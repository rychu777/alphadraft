from pydantic import BaseModel, Field
from typing import Any, Optional

class MatchTimelineSchema(BaseModel):
    id: str = Field(alias="_id")
    region: str
    status: str = "pending"  # pending, downloaded, error, corrupted
    data: Optional[Any] = None