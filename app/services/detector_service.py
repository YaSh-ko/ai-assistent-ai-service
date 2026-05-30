"""
Orchestrates detector agent + session state persistence.
"""
import logging
import string
from typing import Any, Dict, List, Optional

from app.models.detector import (
    DetectedEntity,
    DetectorContext,
    DetectorProposal,
    SessionState,
)
from app.services.detector_agent import DetectorAgent
from app.services.detector_session_service import DetectorSessionService
from app.services.entity_index_service import EntityIndexService
from app.services.session_manager import SessionManager

logger = logging.getLogger(__name__)


# Ignored when tokenizing user text for stale-entity check (title/description overlap).
# Function words that appear in almost any message and must not count as a topic match.
_STOPWORDS = frozenset({
    "очень", "просто", "уже", "ещё", "еще", "тоже", "также", "вообще", "снова",
    "меня", "мне", "себя", "свой", "свою", "своё", "свои", "нам", "нас", "ему",
    "это", "что", "как", "для", "при", "про", "без", "над", "под", "или", "если",
    "бы", "ли", "же", "нет", "да", "не", "ни",
    "было", "была", "были", "буду", "есть", "был", "быть",
    "нужно", "надо", "можно", "нельзя",
    "там", "тут", "где", "когда", "тогда", "потом", "сейчас", "сегодня", "вчера",
})

_UPDATE_SCORE_THRESHOLD = 0.82
_UPDATE_STRONG_SCORE = 0.88
_PUNCT = string.punctuation + "«»—…"


def _tokenize_user_message(text: str) -> List[str]:
    """Split user text into tokens, stripping punctuation (сну, → сну)."""
    tokens: List[str] = []
    for word in text.lower().split():
        cleaned = word.strip(_PUNCT)
        if len(cleaned) > 2 and cleaned not in _STOPWORDS:
            tokens.append(cleaned)
    return tokens


def _titles_similar(a: str, b: str) -> bool:
    na, nb = a.lower().strip(), b.lower().strip()
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    wa, wb = na.split()[:4], nb.split()[:4]
    return len(wa) >= 2 and wa == wb


def _user_message_relates_to_pg_entity(
    existing_title: str,
    last_user_text: str,
    *,
    existing_description: str = "",
) -> bool:
    """True when the user's message plausibly continues an existing PG entity (not just a fuzzy embedding)."""
    combined = f"{existing_title} {existing_description}".lower().strip()
    user = last_user_text.lower()
    user_tokens = _tokenize_user_message(user)
    if not combined or not user_tokens:
        return False
    if any(w in combined for w in user_tokens):
        return True
    if len(combined) >= 4 and combined[:4] in user:
        return True
    title_words = [
        w.strip(_PUNCT)
        for w in combined.split()
        if len(w.strip(_PUNCT)) > 2
    ]
    for w in user_tokens:
        if len(w) >= 3 and w[:3] in combined:
            return True
        if len(w) >= 3:
            for tw in title_words:
                if len(tw) >= 3 and w[:2] == tw[:2] and w[:2] not in {"по", "на", "не", "ни", "от", "до", "из", "за", "при"}:
                    return True
    return False


def apply_existing_entity_update(
    entity: DetectedEntity,
    existing_entities: Optional[List[Dict[str, Any]]],
    last_user_text: str,
) -> DetectedEntity:
    """
    Prefer update over duplicate when semantic search finds a strong match.
    LLM often returns action=create even when existing_entity_id is in the prompt.
    """
    if entity.action == "update" and entity.existing_entity_id:
        if entity.type == "observation" and last_user_text.strip():
            fields = dict(entity.fields or {})
            fields["description"] = last_user_text.strip()
            return entity.model_copy(update={"fields": fields})
        return entity
    if not existing_entities:
        return entity

    typed = [e for e in existing_entities if e.get("entity_type") == entity.type]
    if not typed:
        return entity

    top = typed[0]
    score = float(top.get("score", 0))
    existing_id = top.get("entity_id")
    existing_title = top.get("title") or ""
    existing_description = top.get("description") or ""
    if score < _UPDATE_SCORE_THRESHOLD or not existing_id:
        return entity

    relates = _user_message_relates_to_pg_entity(
        existing_title, last_user_text, existing_description=existing_description,
    )
    titles_align = _titles_similar(entity.title or "", existing_title)
    strong_match = score >= _UPDATE_STRONG_SCORE and (relates or titles_align)
    moderate_match = score >= _UPDATE_SCORE_THRESHOLD and relates

    if not (strong_match or moderate_match):
        logger.info(
            "[DetectorService] Keeping create: semantic score=%.3f but message doesn't relate to %r",
            score, existing_title[:50],
        )
        return entity

    logger.info(
        "[DetectorService] Auto-converting to update: type=%s existing_id=%s score=%.3f relates=%s title=%r",
        entity.type, str(existing_id)[:12], score, relates, existing_title[:50],
    )
    merged_fields = dict(entity.fields or {})
    note_text = last_user_text.strip() or merged_fields.get("description") or entity.description or ""
    return entity.model_copy(update={
        "action": "update",
        "existing_entity_id": existing_id,
        "existing_title": existing_title,
        "title": existing_title or entity.title,
        "fields": {**merged_fields, "description": note_text},
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
    user_tokens = _tokenize_user_message(user)
    if not user_tokens:
        return True

    combined = f"{title} {desc}"
    matches = sum(1 for w in user_tokens if w in combined)
    if matches >= 1:
        return True

    # Substring overlap for inflected Russian (руках / руки / рука)
    if len(title) >= 4 and any(
        title[:4] in user or user_word[:4] in title for user_word in user_tokens
    ):
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

    observation_markers = (
        "заметил", "понял", "осознал", "увидел", "вчера", "сегодня",
        "случил", "произош", "было", "на работе", "обратил внимание",
        "чувствую", "наблюдение", "столкнулся",
    )
    goal_markers = (
        "хочу", "цель", "планиру", "достич", "добиться", "мечтаю",
        "намерен", "стремлюсь", "к лету", "к июн", "направлен",
    )
    task_markers = (
        "попробую", "сделаю", "нужно", "задача", "записаться",
        "шаг", "начну", "в течение недели", "на этой неделе",
    )

    scores = {
        "observation": sum(1 for m in observation_markers if m in last_user),
        "goal": sum(1 for m in goal_markers if m in last_user),
        "task": sum(1 for m in task_markers if m in last_user),
    }
    best_type, best_score = max(scores.items(), key=lambda x: x[1])
    return best_type if best_score > 0 else None


def build_detector_context(session_context: Dict[str, Any], state: SessionState) -> DetectorContext:
    chat_ctx = session_context.get("chat_context") or session_context.get("thread_context") or {}
    entity_type = chat_ctx.get("type") or chat_ctx.get("entity_type")
    entity_id = chat_ctx.get("id") or chat_ctx.get("entity_id")
    return DetectorContext(
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        session_state=state,
        thread_context=chat_ctx if isinstance(chat_ctx, dict) else {},
    )


class DetectorService:
    """High-level API used by runs stream and REST endpoints."""

    def __init__(
        self,
        session_manager: SessionManager,
        detector_agent: Optional[DetectorAgent] = None,
        session_logic: Optional[DetectorSessionService] = None,
        entity_index: Optional[EntityIndexService] = None,
    ):
        self._sessions = session_manager
        self._agent = detector_agent or DetectorAgent()
        self._logic = session_logic or DetectorSessionService()
        self._entity_index = entity_index

    async def run_after_turn(
        self,
        thread_id: str,
        messages: List[Dict[str, Any]],
    ) -> Optional[DetectorProposal]:
        """
        Run detector after an assistant turn; persist state; return chip proposal if ready.
        """
        logger.info(
            "[DetectorService] ========== DETECTOR RUN START ========== thread=%s total_msgs=%d",
            thread_id, len(messages),
        )
        session = await self._sessions.get_session(thread_id)
        if not session:
            logger.warning("[DetectorService] No session for thread %s", thread_id)
            return None

        detector_messages = langgraph_messages_to_detector_format(messages)
        if not detector_messages:
            logger.info("[DetectorService] No detector messages after conversion, skipping")
            return None

        last_user_text = ""
        for msg in reversed(detector_messages):
            if msg.get("role") == "user":
                last_user_text = msg.get("content", "")
                break

        logger.info(
            "[DetectorService] User message: %r (%d chars)",
            last_user_text[:100], len(last_user_text),
        )

        focus_messages = trim_messages_to_last_turn(detector_messages)
        logger.info("[DetectorService] Focus messages: %d (trimmed from %d)", len(focus_messages), len(detector_messages))

        state = load_session_state(session.context or {})
        context = build_detector_context(session.context or {}, state)

        if context.is_event_context:
            context.session_state = state

        preferred_type = guess_focus_type_from_messages(focus_messages)
        if context.is_goal_context:
            preferred_type = "task"

        existing_entities = None
        if self._entity_index and last_user_text:
            user_id = getattr(session, "user_id", None)
            logger.info(
                "[DetectorService] Entity search: user_id=%s query=%r entity_index=%s",
                user_id, last_user_text[:60], "available" if self._entity_index else "none",
            )
            if user_id:
                try:
                    matches = await self._entity_index.search(user_id, last_user_text)
                    if matches:
                        existing_entities = [m.to_dict() for m in matches]
                        logger.info(
                            "[DetectorService] Passing %d existing entities to LLM prompt:",
                            len(matches),
                        )
                        for m in matches:
                            logger.info(
                                "[DetectorService]   [%s] id=%s «%s» score=%.3f",
                                m.entity_type, m.entity_id[:12], m.title[:50], m.score,
                            )
                    else:
                        logger.info("[DetectorService] No similar existing entities found")
                except Exception as e:
                    logger.warning("[DetectorService] Entity search failed: %s", e, exc_info=True)
        elif not self._entity_index:
            logger.debug("[DetectorService] Entity index not configured, skipping search")

        if context.is_goal_context and context.entity_id:
            pinned_goal = {
                "entity_id": context.entity_id,
                "entity_type": "goal",
                "title": context.thread_context.get("title", ""),
                "description": context.thread_context.get("description", ""),
                "status": "active",
            }
            rest = [
                e for e in (existing_entities or [])
                if e.get("entity_id") != context.entity_id
            ]
            existing_entities = [pinned_goal, *rest]

        try:
            detection = await self._agent.detect(
                thread_id=thread_id,
                messages=focus_messages,
                context=context,
                existing_entities=existing_entities,
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

        filtered_entities = []
        for e in detection.entities:
            matches = entity_matches_last_user_message(e, last_user_text)
            if matches:
                filtered_entities.append(e)
            else:
                logger.info(
                    "[DetectorService] Stale entity rejected: type=%s title=%r (doesn't match user msg)",
                    e.type, e.title,
                )
        if detection.entities and not filtered_entities:
            logger.warning(
                "[DetectorService] thread=%s ALL %d entities rejected as stale",
                thread_id, len(detection.entities),
            )
        if existing_entities and last_user_text:
            filtered_entities = [
                apply_existing_entity_update(e, existing_entities, last_user_text)
                for e in filtered_entities
            ]

        if not context.is_goal_context:
            filtered_entities = [e for e in filtered_entities if e.type != "task"]
        elif context.entity_id:
            normalized = []
            for e in filtered_entities:
                if e.type == "goal" and e.action != "update":
                    continue
                if e.type == "goal" and not e.existing_entity_id:
                    e = e.model_copy(
                        update={
                            "action": "update",
                            "existing_entity_id": context.entity_id,
                            "existing_title": context.thread_context.get("title"),
                        }
                    )
                normalized.append(e)
            filtered_entities = normalized

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
                "[DetectorService] ===== CHIP READY ===== thread=%s action=%s type=%s conf=%.2f title=%r existing_id=%s",
                thread_id, proposal.action, proposal.entity_type,
                proposal.confidence, proposal.preview.get("title", ""),
                proposal.existing_entity_id,
            )
        else:
            logger.info("[DetectorService] ========== DETECTOR RUN END (no chip) ========== thread=%s", thread_id)

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
