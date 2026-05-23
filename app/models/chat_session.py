import json
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
    computed_field,
    model_validator,
    ConfigDict,
)

class SessionStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    CLOSED = "closed"

class ChatSession(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    thread_id: str = Field(validation_alias=AliasChoices("thread_id", "session_id"))
    user_id: str
    created_at: datetime
    last_active_at: datetime
    status: str = "active"
    context: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata")
    history: List[Dict[str, Any]] = Field(default_factory=list)
    states: List[Dict[str, Any]] = Field(default_factory=list)
    title: Optional[str] = None

    @computed_field
    @property
    def session_id(self) -> str:
        """Legacy API name for ``thread_id`` (included in JSON)."""
        return self.thread_id

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_row(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "last_active_at" not in data:
            if "updated_at" in data:
                data = {**data, "last_active_at": data["updated_at"]}
            elif "created_at" in data:
                data = {**data, "last_active_at": data["created_at"]}
        if "status" not in data:
            md = data.get("metadata")
            if isinstance(md, str):
                try:
                    md = json.loads(md)
                except Exception:
                    md = {}
            if isinstance(md, dict) and "status" in md:
                data = {**data, "status": md["status"]}
        return data
