"""
Detector Agent — background LLM agent that detects entities (Events, Concepts)
from chat messages and returns structured results.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from app.models.detector import (
    DetectedEntity,
    DetectorContext,
    DetectorResult,
    FieldUpdate,
    SessionState,
)
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

# Confidence thresholds
_EVENT_THRESHOLD_FREE = 0.65       # show soft hint
_EVENT_THRESHOLD_CHIP = 0.85       # show full chip
_EVENT_THRESHOLD_RHIZOME = 0.70    # rhizome context — lower threshold
_CONCEPT_THRESHOLD_CHIP = 0.72     # show concept chip
_CONCEPT_THRESHOLD_AUTO = 0.88     # auto-create in event context

_SYSTEM_PROMPT = """Ты — аналитический агент системы Delёz. Твоя задача — анализировать диалог пользователя с ассистентом и определять, есть ли в нём кандидаты на создание структурированных сущностей.

Ты должен вернуть ТОЛЬКО валидный JSON без каких-либо пояснений.

Типы сущностей:
1. event — реальное событие из жизни пользователя (прошедшее время, эмоциональный контекст, конкретная ситуация)
2. concept — поведенческий вывод/правило (требует ОБА сигнала: негативный опыт И вывод/намерение изменить поведение)

НЕ создавай сущности для:
- технических вопросов ("помоги решить", "что такое")
- гипотетических рассуждений ("а вот если бы")
- чужого опыта без личного эмоционального контекста
- вопросов к ассистенту о его функциях

Формат ответа:
{
  "entities": [
    {
      "type": "event",
      "confidence": 0.91,
      "title": "Краткое название события",
      "fields": {
        "description": "Описание из контекста диалога",
        "eventdate": "YYYY-MM-DD или null",
        "importance": 0.8,
        "sentiment_score": -0.6
      }
    }
  ],
  "updates": []
}

Или для концепта:
{
  "entities": [
    {
      "type": "concept",
      "confidence": 0.88,
      "name": "Краткое название концепта",
      "description": "Развёрнутое объяснение",
      "grounds": [
        {"title": "Причина 1", "severity": 8},
        {"title": "Причина 2", "severity": 6}
      ],
      "transformations": [
        {"title": "Вывод 1", "category": "behaviorChange"},
        {"title": "Вывод 2", "category": "relationshipRule"}
      ],
      "similar_existing": []
    }
  ],
  "updates": []
}

Если ничего не обнаружено — верни: {"entities": [], "updates": []}
Верни ТОЛЬКО JSON, без markdown, без пояснений."""


class DetectorAgent:
    """
    Background LLM agent that detects Events and Concepts from chat messages.
    Called asynchronously after each assistant response.
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        self._llm = llm_service or LLMService()

    async def detect(
        self,
        thread_id: str,
        messages: List[Dict[str, Any]],
        context: DetectorContext,
    ) -> DetectorResult:
        """
        Main detection method. Calls LLM and returns filtered DetectorResult.
        """
        if not messages:
            return DetectorResult()

        # Take last 10 messages max
        recent = messages[-10:]

        prompt = self._build_prompt(recent, context)

        try:
            raw = await self._llm.generate(
                prompt=prompt,
                task_type="simple_question",
                system_prompt=_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=1024,
            )
            result = self._parse_llm_response(raw)
        except Exception as e:
            logger.error(f"[DetectorAgent] LLM call failed for thread {thread_id}: {e}")
            return DetectorResult()

        result = self._apply_session_filters(result, context.session_state)
        result = self._apply_context_rules(result, context)
        result = self._keep_top_entity(result)

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        messages: List[Dict[str, Any]],
        context: DetectorContext,
    ) -> str:
        """Build the user-facing prompt for the LLM."""
        lines = []

        if context.is_event_context:
            lines.append(
                f"Чат открыт в контексте существующего события (ID: {context.entity_id}). "
                "Ищи только детали для обогащения этого события или концепты. "
                "НЕ предлагай создание нового события."
            )
        elif context.is_rhizome_context:
            lines.append(
                "Чат открыт с главного экрана ('Как прошёл твой день?'). "
                "Порог уверенности для событий снижен — будь активнее в обнаружении."
            )
        else:
            lines.append("Свободный чат без привязки к конкретному событию.")

        lines.append("\nПоследние сообщения диалога:")
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role == "user":
                lines.append(f"Пользователь: {content}")
            elif role == "assistant":
                lines.append(f"Ассистент: {content}")

        lines.append(
            "\nПроанализируй диалог и верни JSON с обнаруженными сущностями."
        )
        return "\n".join(lines)

    def _parse_llm_response(self, raw: str) -> DetectorResult:
        """Parse JSON response from LLM into DetectorResult."""
        try:
            # Strip markdown code blocks if present
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            data = json.loads(text)
            entities = [DetectedEntity(**e) for e in data.get("entities", [])]
            updates = [FieldUpdate(**u) for u in data.get("updates", [])]
            return DetectorResult(entities=entities, updates=updates)
        except Exception as e:
            logger.warning(f"[DetectorAgent] Failed to parse LLM response: {e}. Raw: {raw[:200]}")
            return DetectorResult()

    def _apply_session_filters(
        self,
        result: DetectorResult,
        session_state: SessionState,
    ) -> DetectorResult:
        """Remove entities that were already declined in this session."""
        filtered = []
        for entity in result.entities:
            title = entity.title or entity.name or ""
            if session_state.is_declined(title):
                logger.debug(f"[DetectorAgent] Skipping declined entity: {title}")
                continue
            filtered.append(entity)
        return DetectorResult(entities=filtered, updates=result.updates)

    def _apply_context_rules(
        self,
        result: DetectorResult,
        context: DetectorContext,
    ) -> DetectorResult:
        """
        Apply confidence thresholds and context-specific rules.
        - EventContext: drop new event entities, keep concepts and updates
        - RhizomeContext: lower event threshold (0.70)
        - FreeContext: standard thresholds (0.65 soft / 0.85 chip)
        """
        filtered = []
        for entity in result.entities:
            if entity.type == "event":
                if context.is_event_context:
                    # In event context we never create new events
                    continue
                threshold = (
                    _EVENT_THRESHOLD_RHIZOME
                    if context.is_rhizome_context
                    else _EVENT_THRESHOLD_FREE
                )
                if entity.confidence < threshold:
                    continue
            elif entity.type == "concept":
                if entity.confidence < _CONCEPT_THRESHOLD_CHIP:
                    continue
            filtered.append(entity)

        return DetectorResult(entities=filtered, updates=result.updates)

    def _keep_top_entity(self, result: DetectorResult) -> DetectorResult:
        """Keep only the entity with the highest confidence (one per cycle)."""
        if len(result.entities) <= 1:
            return result
        top = max(result.entities, key=lambda e: e.confidence)
        return DetectorResult(entities=[top], updates=result.updates)
