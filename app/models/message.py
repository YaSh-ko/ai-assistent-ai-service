from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from datetime import datetime
import uuid

class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    additional_kwargs: Optional[Dict[str, Any]] = None
