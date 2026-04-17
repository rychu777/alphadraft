from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime

class MatchSummarySchema(BaseModel):
    id: str = Field(alias="_id")
    region: str
    status: str = "pending" # pending, downloaded, error, corrupted
    data: Optional[Any] = None
    game_version: Optional[str] = None