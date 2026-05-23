from pydantic import BaseModel, PrivateAttr, Field
from typing import Dict, Any, Optional, List
from datetime import datetime


class Thread(BaseModel):
    thread_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    status: str = "idle"
    values: Dict[str, Any] = Field(default_factory=dict)

    # Private attribute for storing thread history states (in-memory)
    _states: List[Dict[str, Any]] = PrivateAttr(default_factory=list)

    def update_from_last_state(self):
        """Update the public values field from the latest private state."""
        if self._states:
            self.values = self._states[0].get("values", {})
