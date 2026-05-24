"""
Orchestrates detector agent + session state persistence.
"""
import logging
from typing import Any, Dict, List, Optional

from app.models.detector import (
    DetectedEntity,
    DetectorContext,
    DetectorProposal,
    SessionState,
)
from app.services.detector_agent import DetectorAgent
from app.services.detector_session_service import DetectorSessionService
from app.services.session_manager import SessionManager

logger = logging.getLogger(__name__)


_COMMON_WORDS = frozenset({
    "очень", "хочу", "хотел", "бы", "как", "что", "это", "для", "меня",
    "себя", "мне", "было", "буду", "нужно", "надо", "лету", "летом",
})


def trim_messages_to_last_turn(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detector focuses on the latest user turn (avoids anchoring on older goals)."""
    last_human_idx: Optional[int] = None
    for i, msg in enumerate(messages):
        if msg.get("role") == "user":
            last_human_idx = i
    if last_human_idx is None:
        return messages[-6:]
    return messages[last_human_idx:]


def entity_matches_last_user_message(entity: DetectedEntity, last_user_text: str) -> bool:
    """Reject stale entities from earlier in the conversation (e.g. old goal title)."""
    if not last_user_text.strip():
        return True

    title = (entity.title or entity.name or "").lower()
    desc = (entity.description or (entity.fields or {}).get("description") or "").lower()
    user = last_user_text.lower()

    user_tokens = [w for w in user.split() if len(w) > 2 and w not in _COMMON_WORDS]
    if not user_tokens:
        return True

    combined = f"{title} {desc}"
    matches = sum(1 for w in user_tokens if w in combined)
    if matches >= 1:
        return True

    # Substring overlap for inflected Russian (руках / руки / рука)
    if len(title) >= 4 and any(title[:4] in user or user_word[:4] in title for user_word in user_tokens):
        return True

    logger.warning(
        "[DetectorService] Rejecting stale entity %r for user message %r",
        entity.title,
        last_user_text[:80],
    )
    return False


def langgraph_messages_to_detector_format(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert LangGraph SDK message dicts to detector role/content format."""
    converted: List[Dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        msg_type = msg.get("type") or msg.get("role")
        content = msg.get("content", "")
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            content = " ".join(parts)
        role = "user" if msg_type in ("human", "user") else "assistant"
        if msg_type in ("human", "user", "ai", "assistant") and content:
            converted.append({"role": role, "content": str(content)})
    return converted


def load_session_state(context: Dict[str, Any]) -> SessionState:
    raw = context.get("detector_state") or {}
    if isinstance(raw, SessionState):
        return raw
    try:
        return SessionState.model_validate(raw)
    except Exception as exc:
        logger.warning("[DetectorService] Failed to parse detector_state: %s", exc)
        if isinstance(raw, dict):
            try:
                return SessionState(
                    active=raw.get("active") or raw.get("pending"),
                    shelved=raw.get("shelved") or [],
                    chip_shown_for=raw.get("chip_shown_for"),
                    proposed_entities=raw.get("proposed_entities") or [],
                    created_entities=raw.get("created_entities") or [],
                )
            except Exception:
                pass
        return SessionState()


def guess_focus_type_from_messages(messages: List[Dict[str, Any]]) -> Optional[str]:
    """Heuristic: infer entity type from the latest user message."""
    last_user = None
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user = (msg.get("content") or "").lower()
            break
    if not last_user:
        return None

    event_markers = (
        "вчера", "сегодня", "случил", "произош", "было", "сорвал",
        "конфликт", "встреч", "разговор", "на работе", "событ",
    )
    goal_markers = (
        "хочу", "цель", "планиру", "достич", "добиться", "мечтаю",
        "намерен", "стремлюсь", "к лету", "к июн", "похуд",
    )
    experiment_markers = (
        "попробую", "эксперимент", "гипотез", "проверю", "тестиру",
        "посмотрю что будет", "в течение недели буду",
    )

    scores = {
        "event": sum(1 for m in event_markers if m in last_user),
        "goal": sum(1 for m in goal_markers if m in last_user),
        "experiment": sum(1 for m in experiment_markers if m in last_user),
    }
    best_type, best_score = max(scores.items(), key=lambda x: x[1])
    return best_type if best_score > 0 else None


def build_detector_context(session_context: Dict[str, Any], state: SessionState) -> DetectorContext:
    chat_ctx = session_context.get("chat_context") or session_context.get("thread_context") or {}
    entity_type = chat_ctx.get("type") or chat_ctx.get("entity_type")
    entity_id = chat_ctx.get("id") or chat_ctx.get("entity_id")
    return DetectorContext(
        entity_type=entity_type,
        entity_id=entity_id,
        session_state=state,
    )


class DetectorService:
    """High-level API used by runs stream and REST endpoints."""

    def __init__(
        self,
        session_manager: SessionManager,
        detector_agent: Optional[DetectorAgent] = None,
        session_logic: Optional[DetectorSessionService] = None,
    ):
        self._sessions = session_manager
        self._agent = detector_agent or DetectorAgent()
        self._logic = session_logic or DetectorSessionService()

    async def run_after_turn(
        self,
        thread_id: str,
        messages: List[Dict[str, Any]],
    ) -> Optional[DetectorProposal]:
        """
        Run detector after an assistant turn; persist state; return chip proposal if ready.
        """
        session = await self._sessions.get_session(thread_id)
        if not session:
            logger.warning("[DetectorService] No session for thread %s", thread_id)
            return None

        detector_messages = langgraph_messages_to_detector_format(messages)
        if not detector_messages:
            return None

        last_user_text = ""
        for msg in reversed(detector_messages):
            if msg.get("role") == "user":
                last_user_text = msg.get("content", "")
                break

        focus_messages = trim_messages_to_last_turn(detector_messages)

        state = load_session_state(session.context or {})
        context = build_detector_context(session.context or {}, state)

        if context.is_event_context:
            context.session_state = state

        preferred_type = guess_focus_type_from_messages(focus_messages)

        try:
            detection = await self._agent.detect(
                thread_id=thread_id,
                messages=focus_messages,
                context=context,
            )
        except Exception as e:
            logger.error("[DetectorService] Detection failed: %s", e, exc_info=True)
            return None

        if detection.entities:
            logger.info(
                "[DetectorService] thread=%s entities=%s same_topic=%s preferred=%s focus=%r",
                thread_id,
                [(e.type, round(e.confidence, 2), e.title) for e in detection.entities],
                detection.same_topic_as_pending,
                preferred_type,
                last_user_text[:60],
            )
        else:
            logger.info("[DetectorService] thread=%s no entities detected", thread_id)

        filtered_entities = [
            e for e in detection.entities
            if entity_matches_last_user_message(e, last_user_text)
        ]
        if detection.entities and not filtered_entities:
            logger.warning(
                "[DetectorService] thread=%s all entities rejected as stale",
                thread_id,
            )
        detection = detection.model_copy(update={"entities": filtered_entities})

        new_state, proposal = self._logic.process_detection(
            state,
            detection,
            preferred_type=preferred_type,
            last_user_text=last_user_text,
        )

        fresh = await self._sessions.get_session(thread_id)
        base_context = (fresh.context if fresh else None) or session.context or {}
        merged_context = {
            **base_context,
            "detector_state": new_state.model_dump(mode="json"),
        }
        await self._sessions.update_session(thread_id, {"context": merged_context})

        if proposal and proposal.show_chip:
            logger.info(
                "[DetectorService] Chip ready thread=%s type=%s confidence=%.2f",
                thread_id,
                proposal.entity_type,
                proposal.confidence,
            )
        return proposal if proposal and proposal.show_chip else None

    async def decline_proposal(
        self,
        thread_id: str,
        *,
        title: Optional[str] = None,
        pending_id: Optional[str] = None,
    ) -> bool:
        session = await self._sessions.get_session(thread_id)
        if not session:
            return False
        state = load_session_state(session.context or {})
        new_state = self._logic.decline(state, title=title, pending_id=pending_id)
        fresh = await self._sessions.get_session(thread_id)
        base_context = (fresh.context if fresh else None) or session.context or {}
        merged_context = {
            **base_context,
            "detector_state": new_state.model_dump(mode="json"),
        }
        await self._sessions.update_session(thread_id, {"context": merged_context})
        return True

    async def get_pending_proposal(self, thread_id: str) -> Optional[DetectorProposal]:
        """
        Return last emitted chip for frontend polling.
        Filled when run_after_turn decides to show a chip (including during SSE stream).
        """
        session = await self._sessions.get_session(thread_id)
        if not session:
            return None
        state = load_session_state(session.context or {})
        if state.last_proposal:
            try:
                proposal = DetectorProposal.model_validate(state.last_proposal)
                if proposal.show_chip:
                    return proposal
            except Exception as exc:
                logger.warning("[DetectorService] Invalid last_proposal: %s", exc)
        return None
