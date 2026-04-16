from pydantic import BaseModel, Field

class PlayerSchema(BaseModel):
    # We use PUUID as the MongoDB _id
    id: str = Field(alias="_id")
    server: str
    tier: str
    puuid: str
    last_seen: int # Timestamp of the last scan