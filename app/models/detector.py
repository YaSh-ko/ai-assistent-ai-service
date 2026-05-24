"""
Pydantic models for the Detector Agent.
Defines data structures for entity detection from chat messages.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pydantic import AliasChoices, BaseModel, Field, model_validator


# Confidence thresholds (tunable)
PENDING_START_THRESHOLD = 0.55
CHIP_THRESHOLDS: Dict[str, float] = {
    "event": 0.80,
    "goal": 0.80,
    "experiment": 0.80,
}
SAME_TOPIC_CONFIDENCE_BOOST = 0.12
# Re-show chip for same pending_id if confidence grew by at least this much
CHIP_RESHOW_CONFIDENCE_DELTA = 0.10

# Entity types that participate in pending / confirmation chip flow
CHIP_ENTITY_TYPES = frozenset({"event", "goal", "experiment"})


class ProposedEntity(BaseModel):
    """An entity that was proposed to the user but not yet confirmed."""
    type: str
    proposed_title: str
    status: str = "pending"
    message_id: str = ""


class CreatedEntity(BaseModel):
    """An entity that was already created in this session."""
    type: str
    entity_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PendingCandidate(BaseModel):
    """Accumulated candidate stored in session until user confirms or declines."""
    id: str
    type: str  # event | goal | experiment
    title: str
    fields: Dict[str, Any] = Field(default_factory=dict)
    confidence: float
    message_count: int = 1
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SessionState(BaseModel):
    """
    Detector state inside ChatSession.context['detector_state'].

    - active: current topic candidate (one chip at a time)
    - shelved: parked candidates when user switches topic
    - chip_shown_for: pending_id for which chip was already emitted
    - last_proposal: last chip payload for frontend polling (GET /proposal)
    """
    active: Optional[PendingCandidate] = Field(
        default=None,
        validation_alias=AliasChoices("active", "pending"),
    )
    shelved: List[PendingCandidate] = Field(default_factory=list)
    chip_shown_for: Optional[str] = None
    last_proposal: Optional[Dict[str, Any]] = None
    proposed_entities: List[ProposedEntity] = Field(default_factory=list)
    created_entities: List[CreatedEntity] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_pending(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("pending") and not data.get("active"):
            data = {**data, "active": data["pending"]}
        return data

    @property
    def pending(self) -> Optional[PendingCandidate]:
        """Backward-compatible alias for active."""
        return self.active

    def is_declined(self, title: str) -> bool:
        normalized = title.lower().strip()
        return any(
            e.status == "declined" and e.proposed_title.lower().strip() == normalized
            for e in self.proposed_entities
        )

    def is_declined_id(self, pending_id: str) -> bool:
        return any(
            e.status == "declined" and e.message_id == pending_id
            for e in self.proposed_entities
        )

    def get_created_event_id(self) -> Optional[str]:
        for e in self.created_entities:
            if e.type == "event":
                return e.entity_id
        return None


class DetectorContext(BaseModel):
    """Context passed to the detector describing the current chat mode."""
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    session_state: SessionState = Field(default_factory=SessionState)

    @property
    def is_event_context(self) -> bool:
        return self.entity_id is not None and self.entity_type in (None, "event", "entry")

    @property
    def is_rhizome_context(self) -> bool:
        return self.entity_type == "event" and self.entity_id is None


class DetectedEntity(BaseModel):
    """A single entity detected by the LLM."""
    type: str
    confidence: float
    title: Optional[str] = None
    fields: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    target_date: Optional[str] = None
    priority: Optional[str] = None
    hypothesis: Optional[str] = None
    name: Optional[str] = None
    grounds: Optional[List[Dict[str, Any]]] = None
    transformations: Optional[List[Dict[str, Any]]] = None
    similar_existing: Optional[List[Dict[str, Any]]] = None


class FieldUpdate(BaseModel):
    entity_id: str
    field: str
    value: Any
    confidence: float


class DetectorResult(BaseModel):
    entities: List[DetectedEntity] = []
    updates: List[FieldUpdate] = []
    same_topic_as_pending: bool = False

    def has_content(self) -> bool:
        return bool(self.entities or self.updates)


class DetectorProposal(BaseModel):
    """Payload for frontend confirmation chip (SSE event detector_proposal)."""
    show_chip: bool = False
    action: str = "confirm_create"
    entity_type: str = ""
    confidence: float = 0.0
    pending_id: str = ""
    preview: Dict[str, Any] = Field(default_factory=dict)
    revived: bool = False


class DetectEntitiesRequest(BaseModel):
    thread_id: str
    messages: List[Dict[str, Any]]
    context: DetectorContext = Field(default_factory=DetectorContext)


class DeclineProposalRequest(BaseModel):
    thread_id: str
    title: Optional[str] = None
    pending_id: Optional[str] = None
