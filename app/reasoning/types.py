from typing import Any, Dict, List, Optional, TypedDict
from enum import Enum


class ReasoningStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class ReasoningStep(TypedDict):
    """Structure for a single reasoning step."""
    step_number: int
    description: str
    action: str
    action_input: Any
    observation: Any
    thought: str
    duration_ms: float
    status: ReasoningStatus
    metadata: Optional[Dict[str, Any]]

class CoTState(TypedDict):
    """Structure for storing state between steps."""
    steps: List[ReasoningStep]
    context: Dict[str, Any]
    variables: Dict[str, Any]
    history: List[Dict[str, Any]]

class ReasoningResult(TypedDict):
    """Final result of the reasoning process."""
    answer: Any
    steps: List[ReasoningStep]
    total_duration_ms: float
    total_tokens: int
    metadata: Dict[str, Any]
    status: ReasoningStatus
    error: Optional[str]
