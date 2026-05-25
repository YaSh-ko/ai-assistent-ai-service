"""
Manages active/shelved detector candidates and confidence accumulation per chat thread.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from app.models.detector import (
    CHIP_ENTITY_TYPES,
    CHIP_THRESHOLDS,
    PENDING_START_THRESHOLD,
    SAME_TOPIC_CONFIDENCE_BOOST,
    CreatedEntity,
    DetectedEntity,
    DetectorProposal,
    DetectorResult,
    PendingCandidate,
    ProposedEntity,
    SessionState,
)

logger = logging.getLogger(__name__)


def _normalize_title(title: str) -> str:
    return title.lower().strip()


def _titles_similar(a: str, b: str) -> bool:
    na, nb = _normalize_title(a), _normalize_title(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    wa, wb = na.split()[:4], nb.split()[:4]
    return len(wa) >= 2 and wa == wb


def _entity_display_title(entity: DetectedEntity) -> str:
    return (entity.title or entity.name or "").strip()


def _entity_fields(entity: DetectedEntity) -> dict:
    fields: dict = dict(entity.fields or {})
    if entity.description and "description" not in fields:
        fields["description"] = entity.description
    if entity.target_date:
        fields["target_date"] = entity.target_date
    if entity.deadline:
        fields["deadline"] = entity.deadline
    if entity.priority:
        fields["priority"] = entity.priority
    if entity.measurable:
        fields["measurable"] = entity.measurable
    if entity.area:
        fields["area"] = entity.area
    if entity.type == "goal" and "status" not in fields:
        fields["status"] = "active"
    if entity.type == "task" and "status" not in fields:
        fields["status"] = "todo"
    return fields


def build_preview(candidate: PendingCandidate) -> dict:
    preview: dict = {"title": candidate.title, **candidate.fields}
    if candidate.type == "observation":
        preview["event_date"] = (
            candidate.fields.get("event_date")
            or candidate.fields.get("eventdate")
        )
    if candidate.type == "task":
        preview["deadline"] = candidate.fields.get("deadline")
    return preview


class DetectorSessionService:
    """Active + shelved candidate model with chip emission rules."""

    def process_detection(
        self,
        session_state: SessionState,
        detection: DetectorResult,
        *,
        preferred_type: Optional[str] = None,
        last_user_text: str = "",
    ) -> Tuple[SessionState, Optional[DetectorProposal]]:
        state = session_state.model_copy(deep=True)
        chip_entity = self._pick_chip_entity(detection, preferred_type=preferred_type)
        if chip_entity is None:
            logger.info("[DetectorSession] No chip entity in LLM result (all filtered or empty)")
            return state, None

        title = _entity_display_title(chip_entity)
        logger.info(
            "[DetectorSession] === Processing chip entity === type=%s action=%s conf=%.2f title=%r existing_id=%s",
            chip_entity.type, chip_entity.action, chip_entity.confidence, title,
            chip_entity.existing_entity_id,
        )

        if not title:
            logger.info("[DetectorSession] Rejected: empty title")
            return state, None
        if state.is_declined(title):
            logger.info("[DetectorSession] Rejected: title previously declined: %r", title)
            return state, None
        if chip_entity.confidence < PENDING_START_THRESHOLD:
            logger.info(
                "[DetectorSession] Rejected: below pending threshold %.2f < %.2f",
                chip_entity.confidence, PENDING_START_THRESHOLD,
            )
            return state, None

        shelved_idx = self._find_shelved_index(state.shelved, chip_entity, detection)

        titles_match = _titles_similar(state.active.title, title) if state.active else False
        llm_says_same = detection.same_topic_as_pending

        same_type_new_topic = (
            state.active is not None
            and state.active.type == chip_entity.type
            and not titles_match
            and not llm_says_same
        )
        topic_switch = (
            shelved_idx is None
            and state.active is not None
            and (
                state.active.type != chip_entity.type
                or same_type_new_topic
            )
        )

        if state.active and state.active.type == chip_entity.type and not titles_match and llm_says_same:
            logger.info(
                "[DetectorSession] LLM says same topic despite different titles: %r → %r (trusting LLM)",
                state.active.title, title,
            )

        if same_type_new_topic:
            detection = detection.model_copy(update={"same_topic_as_pending": False})
            logger.info(
                "[DetectorSession] New %s topic (was: %s)",
                chip_entity.type,
                state.active.title,
            )
        if topic_switch:
            detection = detection.model_copy(update={"same_topic_as_pending": False})
            logger.info(
                "[DetectorSession] Topic switch %s -> %s",
                state.active.type,
                chip_entity.type,
            )

        revived = False
        match_active = (
            shelved_idx is None
            and not topic_switch
            and self._matches_candidate(
                state.active, chip_entity, detection.same_topic_as_pending
            )
        )

        if match_active and state.active:
            state.active = self._reinforce_pending(state.active, chip_entity)
        elif shelved_idx is not None:
            if state.active and state.active.id != state.shelved[shelved_idx].id:
                self._shelve(state, state.active)
            restored = state.shelved.pop(shelved_idx)
            state.active = self._reinforce_pending(restored, chip_entity)
            revived = True
            logger.debug("[Detector] Restored shelved candidate: %s", state.active.title)
        else:
            if state.active and not match_active:
                self._shelve(state, state.active)
            state.active = self._new_pending(chip_entity)

        if not state.active:
            logger.info("[DetectorSession] No active candidate after processing")
            return state, None

        chip_threshold = CHIP_THRESHOLDS.get(state.active.type, 0.85)
        logger.info(
            "[DetectorSession] Active candidate: type=%s action=%s conf=%.2f threshold=%.2f title=%r existing_id=%s",
            state.active.type, state.active.action, state.active.confidence,
            chip_threshold, state.active.title, state.active.existing_entity_id,
        )

        if state.active.confidence < chip_threshold:
            logger.info(
                "[DetectorSession] Below chip threshold: %.2f < %.2f — accumulating, no chip yet",
                state.active.confidence, chip_threshold,
            )
            return state, None

        if not self._should_emit_chip(state, revived=revived, topic_switch=topic_switch):
            logger.info(
                "[DetectorSession] Chip suppressed: id=%s already shown (chip_shown_for=%s, action=%s, shown_action=%s)",
                state.active.id, state.chip_shown_for,
                state.active.action, state.chip_shown_action,
            )
            return state, None

        state.chip_shown_for = state.active.id
        state.chip_shown_action = state.active.action or "create"
        is_update = state.active.action == "update" and state.active.existing_entity_id
        proposal = DetectorProposal(
            show_chip=True,
            action="confirm_update" if is_update else "confirm_create",
            entity_type=state.active.type,
            confidence=round(state.active.confidence, 3),
            pending_id=state.active.id,
            preview=build_preview(state.active),
            revived=revived,
            existing_entity_id=state.active.existing_entity_id if is_update else None,
            existing_title=(state.active.existing_title or state.active.title) if is_update else None,
        )
        state.last_proposal = proposal.model_dump(mode="json")
        logger.info(
            "[DetectorSession] === EMITTING CHIP === action=%s type=%s conf=%.2f title=%r is_update=%s existing_id=%s revived=%s",
            proposal.action, state.active.type, state.active.confidence,
            state.active.title, is_update, state.active.existing_entity_id, revived,
        )
        return state, proposal

    def decline(
        self,
        session_state: SessionState,
        *,
        title: Optional[str] = None,
        pending_id: Optional[str] = None,
    ) -> SessionState:
        state = session_state.model_copy(deep=True)
        declined_title: Optional[str] = title
        declined_type = "observation"

        if pending_id:
            if state.active and state.active.id == pending_id:
                declined_title = declined_title or state.active.title
                declined_type = state.active.type
                state.active = None
            for s in state.shelved:
                if s.id == pending_id:
                    declined_title = declined_title or s.title
                    declined_type = s.type
                    break
            state.shelved = [s for s in state.shelved if s.id != pending_id]
            if state.chip_shown_for == pending_id:
                state.chip_shown_for = None
                state.chip_shown_action = None
        elif state.active:
            declined_title = declined_title or state.active.title
            declined_type = state.active.type
            if state.chip_shown_for == state.active.id:
                state.chip_shown_for = None
                state.chip_shown_action = None
            state.active = None

        if declined_title:
            state.proposed_entities.append(
                ProposedEntity(
                    type=declined_type,
                    proposed_title=declined_title,
                    status="declined",
                    message_id=pending_id or "",
                )
            )
        state.last_proposal = None
        return state

    def mark_created(
        self,
        session_state: SessionState,
        entity_type: str,
        entity_id: str,
        title: str,
        pending_id: Optional[str] = None,
    ) -> SessionState:
        state = session_state.model_copy(deep=True)
        pid = pending_id
        if state.active and (not pid or state.active.id == pid):
            pid = state.active.id
            state.active = None
        if pid:
            state.shelved = [s for s in state.shelved if s.id != pid]
        state.chip_shown_for = None
        state.chip_shown_action = None
        state.last_proposal = None
        state.created_entities.append(CreatedEntity(type=entity_type, entity_id=entity_id))
        state.proposed_entities.append(
            ProposedEntity(
                type=entity_type,
                proposed_title=title,
                status="created",
                message_id=pid or "",
            )
        )
        return state

    def _should_emit_chip(
        self,
        state: SessionState,
        *,
        revived: bool,
        topic_switch: bool = False,
    ) -> bool:
        if not state.active:
            return False
        if revived or topic_switch:
            return True
        if state.chip_shown_for != state.active.id:
            return True
        current_action = state.active.action or "create"
        if state.chip_shown_action and state.chip_shown_action != current_action:
            logger.info(
                "[DetectorSession] Action changed %s → %s — re-emitting chip",
                state.chip_shown_action, current_action,
            )
            return True
        return False

    def _matches_candidate(
        self,
        candidate: Optional[PendingCandidate],
        entity: DetectedEntity,
        same_topic_flag: bool,
    ) -> bool:
        if not candidate:
            return False
        title = _entity_display_title(entity)
        if candidate.type != entity.type:
            return False
        if same_topic_flag:
            return True
        return _titles_similar(candidate.title, title)

    def _find_shelved_index(
        self,
        shelved: List[PendingCandidate],
        entity: DetectedEntity,
        detection: DetectorResult,
    ) -> Optional[int]:
        title = _entity_display_title(entity)
        for i, candidate in enumerate(shelved):
            if candidate.type != entity.type:
                continue
            if detection.same_topic_as_pending and _titles_similar(candidate.title, title):
                return i
            if _titles_similar(candidate.title, title):
                return i
        return None

    def _shelve(self, state: SessionState, candidate: PendingCandidate) -> None:
        if any(s.id == candidate.id for s in state.shelved):
            return
        state.shelved.append(candidate)
        logger.debug("[Detector] Shelved candidate: %s (%s)", candidate.title, candidate.type)

    def _pick_chip_entity(
        self,
        detection: DetectorResult,
        *,
        preferred_type: Optional[str] = None,
    ) -> Optional[DetectedEntity]:
        candidates = [
            e for e in detection.entities
            if e.type in CHIP_ENTITY_TYPES and _entity_display_title(e)
        ]
        if not candidates:
            return None
        if preferred_type:
            typed = [c for c in candidates if c.type == preferred_type]
            if typed:
                return max(typed, key=lambda e: e.confidence)
        return max(candidates, key=lambda e: e.confidence)

    def _new_pending(self, entity: DetectedEntity) -> PendingCandidate:
        return PendingCandidate(
            id=str(uuid.uuid4()),
            type=entity.type,
            title=_entity_display_title(entity),
            fields=_entity_fields(entity),
            confidence=entity.confidence,
            message_count=1,
            updated_at=datetime.now(timezone.utc).isoformat(),
            action=entity.action or "create",
            existing_entity_id=entity.existing_entity_id,
            existing_title=entity.existing_title,
        )

    def _reinforce_pending(
        self,
        pending: PendingCandidate,
        entity: DetectedEntity,
    ) -> PendingCandidate:
        merged_fields = {**pending.fields, **_entity_fields(entity)}
        new_confidence = min(
            1.0,
            max(pending.confidence, entity.confidence) + SAME_TOPIC_CONFIDENCE_BOOST,
        )
        title = pending.title
        if entity.confidence > pending.confidence and _entity_display_title(entity):
            title = _entity_display_title(entity)
        new_action = entity.action or pending.action or "create"
        new_existing_id = entity.existing_entity_id or pending.existing_entity_id
        new_existing_title = entity.existing_title or pending.existing_title

        return PendingCandidate(
            id=pending.id,
            type=pending.type,
            title=title,
            fields=merged_fields,
            confidence=new_confidence,
            message_count=pending.message_count + 1,
            updated_at=datetime.now(timezone.utc).isoformat(),
            action=new_action,
            existing_entity_id=new_existing_id,
            existing_title=new_existing_title,
        )
