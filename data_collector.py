import os
import time
import datetime
import requests
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv

# Import our updated schema
from schemas.player_schema import PlayerSchema
from schemas.match_summary_schema import MatchSummarySchema

load_dotenv()

class RiotDataCollector:
    def __init__(self):
        self.api_key = os.getenv("RIOT_API_KEY")
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://mongodb:27017/")
        self.request_delay = float(os.getenv("API_REQUEST_DELAY", 1.21))
        self.patch_start = int(os.getenv("PATCH_START_TIME", 0))
        self.patch_end = int(os.getenv("PATCH_END_TIME", 0))

        if not self.api_key:
            raise ValueError("Missing RIOT_API_KEY in .env file!")
            
        self.headers = {"X-Riot-Token": self.api_key}
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client["riot_data"]
        self.players_col = self.db["players"]
        self.matches_col = self.db["match_summaries"]
        self.matches_col.create_index("status")

        self.regions = {
            "EUW": "euw1",
            "EUNE": "eun1",
            "KR": "kr",
            "NA": "na1",
            "VN": "vn2",
            # "BR": "br1",
        }

        self.routing_map = {
            "euw1": "europe",
            "eun1": "europe",
            "kr": "asia",
            "na1": "americas",
            "vn2": "sea",
            # "br1": "americas",
        }
        
        self.queue = "RANKED_SOLO_5x5"

    def _make_request(self, url, params=None):
        """
        Improved request handler with support for Rate Limits (429) 
        and Server Timeouts (5xx).
        """
        retries = 5  # Number of retries for 5xx errors
        backoff = 2  # Starting wait time in seconds

        while True:
            response = requests.get(url, headers=self.headers, params=params)
            
            # 1. SUCCESS
            if response.status_code == 200:
                if self.request_delay > 0:
                    time.sleep(self.request_delay)
                return response.json()
                
            # 2. RATE LIMIT (429)
            elif response.status_code == 429:
                sleep_time = int(response.headers.get("Retry-After", 10))
                print(f"[Rate Limit 429] Waiting {sleep_time}s...")
                time.sleep(sleep_time)
                
            # 3. SERVER ERROR / TIMEOUT (500, 502, 503, 504)
            elif 500 <= response.status_code < 600:
                if retries > 0:
                    print(f"[Server Error {response.status_code}] URL: {url}. "
                        f"Retrying in {backoff}s... (Retries left: {retries})")
                    time.sleep(backoff)
                    retries -= 1
                    backoff *= 2  # Wait longer each time (2, 4, 8, 16s)
                else:
                    print(f"[Critical Error] Server {response.status_code} persisted. Skipping.")
                    return None
            
            # 4. OTHER ERRORS (404, 403, etc.)
            else:
                print(f"HTTP Error {response.status_code} for URL: {url}")
                return None

    def save_players_to_mongo(self, entries, server, tier, scan_time):
        """Saves players using puuid as the primary key and updates last_seen timestamp."""
        if not entries:
            return 0

        operations = []
        for entry in entries:
            puuid = entry.get("puuid")
            if not puuid:
                continue

            # Create schema object
            player = PlayerSchema(
                _id=puuid,
                puuid=puuid,
                server=server,
                tier=tier,
                last_seen=scan_time
            )
            
            # Update tier and last_seen if player exists, otherwise insert
            operations.append(UpdateOne(
                {"_id": player.id},
                {"$set": player.model_dump(by_alias=True)},
                upsert=True
            ))
        
        if operations:
            result = self.players_col.bulk_write(operations)
            return len(operations)
        return 0

    def cleanup_demoted_players(self, server, session_start_time):
        """Removes players from the database who were not seen in the current scan session."""
        result = self.players_col.delete_many({
            "server": server,
            "last_seen": {"$lt": session_start_time}
        })
        if result.deleted_count > 0:
            print(f"Cleanup [{server}]: Removed {result.deleted_count} players who demoted from D1+.")

    def get_apex_tier_players(self, region_code, tier, scan_time):
        """Fetches Challenger, Grandmaster, or Master league (Full list)."""
        url = f"https://{region_code}.api.riotgames.com/lol/league/v4/{tier}leagues/by-queue/{self.queue}"
        data = self._make_request(url)
        if data and "entries" in data:
            count = self.save_players_to_mongo(data["entries"], region_code, tier.upper(), scan_time)
            print(f"Database [{region_code} - {tier.upper()}]: Processed {count} players.")
            return count
        return 0

    def get_diamond_1_players(self, region_code, scan_time):
        """Fetches Diamond 1 players using pagination."""
        total = 0
        page = 1
        while True:
            url = f"https://{region_code}.api.riotgames.com/lol/league/v4/entries/{self.queue}/DIAMOND/I"
            data = self._make_request(url, params={"page": page})
            if not data:
                break
            
            count = self.save_players_to_mongo(data, region_code, "DIAMOND_1", scan_time)
            total += count
            if page % 10 == 0:
                print(f"[{region_code}] Diamond 1: Page {page} fetched (Total: {total}).")
            page += 1
        print(f"[{region_code}] Finished Diamond 1. Total: {total} players.")
        return total

    def collect_all(self):
        """Main execution loop for all regions and target tiers."""
        # session_start uses the current timestamp to identify players seen in this run
        session_start = int(datetime.datetime.now().timestamp())
        for name, code in self.regions.items():
            
            print(f"\n{'='*40}\nProcessing region: {name} ({code})\n{'='*40}")
            
            # Fetch Apex tiers
            for tier in ["challenger", "grandmaster", "master"]:
                self.get_apex_tier_players(code, tier, session_start)
            
            # Fetch Diamond 1
            self.get_diamond_1_players(code, session_start)
            
            # Remove players who were in the DB but are no longer in D1+ on this server
            self.cleanup_demoted_players(code, session_start)

    def _get_match_ids_for_player(self, puuid, region_routing):
        """Fetches Solo/Duo match IDs for a given time range."""
        url = f"https://{region_routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        all_match_ids = []
        start_index = 0
        
        while True:
            params = {
                "startTime": self.patch_start,
                "endTime": self.patch_end,
                "queue": 420,  # 420 = Ranked Solo/Duo 5x5
                "start": start_index,
                "count": 100   # Maximum value allowed by Riot
            }
            
            # Using the improved request method with retries
            data = self._make_request(url, params=params)
            
            # If a 5xx/404 error occurs or no data is returned, break the loop for this player
            if data is None or not data:
                break
                
            all_match_ids.extend(data)
            
            # If Riot returns less than 100 matches, there are no more pages to fetch
            if len(data) < 100:
                break
                
            start_index += 100
            
        return all_match_ids

    def collect_matches(self):
        """Iterates over all players and saves their unique matches."""
        if not self.patch_start or not self.patch_end:
            print("[Error] PATCH_START_TIME or PATCH_END_TIME are not set in the .env file!")
            return

        print(f"\n{'='*40}\nStarting match collection\n{'='*40}")
        
        players = self.players_col.find()
        total_players = self.players_col.count_documents({})
        
        processed_count = 0
        total_new_matches = 0

        for player in players:
            puuid = player.get("puuid")
            platform = player.get("server")
            region_routing = self.routing_map.get(platform)
            
            if not puuid or not region_routing:
                continue
                
            m_ids = self._get_match_ids_for_player(puuid, region_routing)
            
            if m_ids:
                operations = []
                for mid in m_ids:
                    # Using the target MatchSummarySchema
                    match_entry = MatchSummarySchema(
                        _id=mid,
                        region=region_routing,
                        status="pending"
                    )
                    
                    operations.append(UpdateOne(
                        {"_id": match_entry.id},
                        {"$set": match_entry.model_dump(by_alias=True)},
                        upsert=True
                    ))
                
                if operations:
                    try:
                        # ordered=False allows us to ignore duplicates during bulk_write
                        result = self.matches_col.bulk_write(operations, ordered=False)
                        total_new_matches += result.upserted_count
                    except Exception as e:
                        # Catch write errors at the MongoDB level
                        pass
            
            processed_count += 1
            if processed_count % 50 == 0:
                print(f"Progress: {processed_count}/{total_players} players | New unique matches: {total_new_matches}")
                
        print(f"\n--- MATCH COLLECTION FINISHED | Total new games: {total_new_matches} ---")

if __name__ == "__main__":
    collector = RiotDataCollector()

    #collector.collect_all()
    #print("\n--- ALL PLAYERS COLLECTED AND DATABASE CLEANED ---")

    collector.collect_matches()
    print("\n--- ALL MATCH IDS COLLECTED ---")
    