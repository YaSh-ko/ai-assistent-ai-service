from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field

class ReasoningStep(BaseModel):
    step_number: int
    question: Optional[str] = None
    answer: Optional[str] = None
    description: Optional[str] = None
    thought: Optional[str] = None
    observation: Optional[str] = None
    sources: List[str] = Field(default_factory=list)
    time_ms: Optional[float] = None

class ReasoningData(BaseModel):
    type: str = "simple_qa"
    steps: List[ReasoningStep] = Field(default_factory=list)
    confidence_score: Optional[float] = None
    total_time_ms: Optional[float] = None

class RagEvent(BaseModel):
    id: Optional[str] = None
    date: Optional[str] = None
    summary: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None

class SourceData(BaseModel):
    rag_events: List[RagEvent] = Field(default_factory=list)
    cag_selected: List[int] = Field(default_factory=list)
    data_sources: List[str] = Field(default_factory=list)
    graph_insights: List[Dict[str, Any]] = Field(default_factory=list)

class ResponseMetadata(BaseModel):
    model_used: str
    tokens: Dict[str, int] = Field(default_factory=dict)
    streaming: bool = False
    session_duration_ms: Optional[float] = None
    complexity: Optional[str] = None

class ChatResponse(BaseModel):
    session_id: str
    user_message: str
    assistant_response: str
    reasoning: Optional[ReasoningData] = None
    sources: Optional[SourceData] = None
    metadata: Optional[ResponseMetadata] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
