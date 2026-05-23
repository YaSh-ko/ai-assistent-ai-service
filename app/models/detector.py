"""
Pydantic models for the Detector Agent.
Defines data structures for entity detection from chat messages.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class ProposedEntity(BaseModel):
    """An entity that was proposed to the user but not yet confirmed."""
    type: str                    # "event" | "concept"
    proposed_title: str
    status: str = "pending"      # "pending" | "declined" | "created"
    message_id: str = ""


class CreatedEntity(BaseModel):
    """An entity that was already created in this session."""
    type: str                    # "event" | "concept"
    entity_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SessionState(BaseModel):
    """Detector state stored inside ChatSession.context['detector_state']."""
    proposed_entities: List[ProposedEntity] = []
    created_entities: List[CreatedEntity] = []

    def is_declined(self, title: str) -> bool:
        """Check if an entity with this title was already declined."""
        return any(
            e.status == "declined" and e.proposed_title.lower() == title.lower()
            for e in self.proposed_entities
        )

    def get_created_event_id(self) -> Optional[str]:
        """Return entity_id of the first created event in this session, if any."""
        for e in self.created_entities:
            if e.type == "event":
                return e.entity_id
        return None


class DetectorContext(BaseModel):
    """Context passed to the detector describing the current chat mode."""
    entity_type: Optional[str] = None   # "event" | None
    entity_id: Optional[str] = None     # ID of existing event (EventContext mode)
    session_state: SessionState = Field(default_factory=SessionState)

    @property
    def is_event_context(self) -> bool:
        """Chat was opened from an event page — enrichment mode only."""
        return self.entity_id is not None

    @property
    def is_rhizome_context(self) -> bool:
        """Chat opened from rhizome main screen — lower confidence threshold."""
        return self.entity_type == "event" and self.entity_id is None


class DetectedEntity(BaseModel):
    """A single entity detected by the LLM."""
    type: str                                       # "event" | "concept"
    confidence: float                               # 0.0 – 1.0
    # Event fields
    title: Optional[str] = None
    fields: Optional[Dict[str, Any]] = None         # eventdate, description, importance, sentiment_score
    # Concept fields
    name: Optional[str] = None
    description: Optional[str] = None
    grounds: Optional[List[Dict[str, Any]]] = None          # NegativeImpacts
    transformations: Optional[List[Dict[str, Any]]] = None  # Transformations
    similar_existing: Optional[List[Dict[str, Any]]] = None # Similar concepts already saved


class FieldUpdate(BaseModel):
    """A silent field update for an existing event (enrichment mode)."""
    entity_id: str
    field: str          # "description" | "event_date" | "title"
    value: Any
    confidence: float


class DetectorResult(BaseModel):
    """Full result returned by DetectorAgent.detect()."""
    entities: List[DetectedEntity] = []
    updates: List[FieldUpdate] = []

    def has_content(self) -> bool:
        return bool(self.entities or self.updates)


class DetectEntitiesRequest(BaseModel):
    """Request body for POST /api/v1/ai/detect-entities."""
    thread_id: str
    messages: List[Dict[str, Any]]      # last N messages from the session
    context: DetectorContext = Field(default_factory=DetectorContext)
