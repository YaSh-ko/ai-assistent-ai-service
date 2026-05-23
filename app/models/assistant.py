from pydantic import BaseModel
from typing import Dict, Any, Optional

class Assistant(BaseModel):
    assistant_id: str
    name: str
    config: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
