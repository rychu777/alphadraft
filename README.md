# AlphaDraft
Hybrid Decision Support Systems: Modeling Global Meta-Game Dynamics using Heterogeneous Graph Neural Networks

## Abstract
**AlphaDraft** is an advanced decision-support system designed to model and optimize the drafting phase in *League of Legends*. By integrating Heterogeneous Graph Neural Networks (GNN) with Large Language Models (LLM), the project moves beyond flat win-rate statistics. It focuses on the semantic and mechanical interactions between champion abilities to predict match outcomes and simulate optimal adversarial drafting strategies.

## Motivation & Research Question
This project is a direct evolution of my previous work, [15-Min Gamba](https://github.com/rychu777/15-min-gamba), which demonstrated that match outcomes are highly predictable based on the game state at the 15-minute mark. 

**The Research Question:** If a game is mathematically determined by early-game differentials (GD@15/XP@15), to what extent is this trajectory predetermined during Champion Select? AlphaDraft aims to quantify the "Draft Diff" by approximating a win-probability heuristic from minute zero.

## Technical Architecture

### 1. Semantic Knowledge Extraction (LLM Layer)
Traditional models suffer from the "Cold Start" problem—they cannot accurately evaluate new or reworked champions due to lack of historical data. AlphaDraft solves this by:
* Using LLMs to parse raw ability descriptions from Data Dragon.
* Extracting mechanical tags (e.g., *displacement, spell-shield, execute, zone-control*).
* Calculating Power Budget Weights based on base cooldowns ($w_i = \frac{CD_i}{\sum CD_j}$).

### 2. Heterogeneous Graph Structure
The game state is represented as a multi-layered graph, explicitly separating intra-team dynamics from inter-team dynamics to capture the complex trade-offs in drafting:
* **Nodes:**
    * **Champion Nodes:** Containing global stats (WR, PR, GD@15) and team affiliation (Blue/Red).
    * **Skill Nodes:** Containing mechanical features and cooldown weights.
* **Edges (Logical Relations):**
    * `Champion -> has_skill -> Skill` (Structural mapping)
    * `Skill -> synergizes_with -> Skill` (Intra-team semantic relations, e.g., *knock-up* + *air-combo*)
    * `Skill -> counters -> Skill` (Inter-team semantic relations, e.g., *spell-shield* vs. *hook*)
    * `Champion -> vs -> Champion` (Empirical historical matchup data)

### 3. The Model: Heterogeneous Graph Attention Networks (HAN/GAT)
We utilize Heterogeneous Graph Attention Networks to allow the model to learn distinct weight matrices for different edge types. This enables the model to dynamically weigh the trade-offs between maximizing intra-team synergies and exploiting inter-team counters. For example, the attention mechanism can prioritize the inter-team `counters` interaction ("Spell Shield vs. Hook" in a Morgana vs. Blitzcrank matchup) while simultaneously evaluating the intra-team `synergizes_with` edges within the same composition.

### 4. Adversarial Search (Minimax)
The trained GNN acts as a Heuristic Evaluation Function. We implement an adversarial simulator using Minimax with Alpha-Beta Pruning to suggest the optimal $n+1$ pick, anticipating the opponent's most likely responses.

## Data Pipeline & Methodology
To achieve statistical significance, the project processes:
* **Dataset:** ~1,000,000 High-ELO matches (Diamond 1 to Challenger).
* **Regions:** KR, EUW, NA, EUNE, BR, VN.
* **Ground Truth:** We use Match-V5 Timeline data. Instead of just "Win/Loss", the model is trained to predict the probability of achieving a positive GD@15/XP@15, which serves as a more granular proxy for draft success.

## Tech Stack
* **Database:** MongoDB (Data Lake for JSON Match/Timeline objects).
* **ML Framework:** PyTorch & PyTorch Geometric (GNN implementation).
* **Data Processing:** Motor (Asynchronous MongoDB driver), Pandas, Scikit-learn.
* **LLM Integration:** Google Gemini Pro API (Semantic feature extraction).

## Academic Context
This project is being developed as a Master's Thesis at Wroclaw University of Science and Technology. It explores the intersection of Supervised Learning and Multi-Agent Decision Theory in imperfect information environments.

---
*AlphaDraft isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc.*
