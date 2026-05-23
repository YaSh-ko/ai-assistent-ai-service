from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime

class Run(BaseModel):
    run_id: str
    thread_id: str
    status: str
    created_at: datetime
    kwargs: Optional[Dict[str, Any]] = None
