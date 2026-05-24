"""
Detector Agent — background LLM agent that detects entities (events, goals, experiments)
from chat messages and returns structured results.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from app.models.detector import (
    CHIP_ENTITY_TYPES,
    DetectedEntity,
    DetectorContext,
    DetectorResult,
    FieldUpdate,
    SessionState,
)
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

# Minimum confidence after LLM call (before session accumulation)
_EVENT_THRESHOLD_FREE = 0.55
_EVENT_THRESHOLD_RHIZOME = 0.50
_GOAL_THRESHOLD = 0.55
_EXPERIMENT_THRESHOLD = 0.55
_CONCEPT_THRESHOLD_CHIP = 0.72

_SYSTEM_PROMPT = """Ты — аналитический агент системы Delёz (инструмент личного роста).
Анализируй диалог и определяй, есть ли кандидаты на создание структурированных сущностей.

Верни ТОЛЬКО валидный JSON без пояснений.

Типы сущностей:
1. event — конкретный опыт, ситуация, достижение или трудность из жизни пользователя
2. goal — цель или намерение (SMART: что хочет достичь, срок, приоритет)
3. experiment — гипотеза или эксперимент («попробую X и посмотрю на результат Y»)
4. concept — вывод/правило из опыта (только если есть и ситуация, и намерение измениться)

НЕ создавай сущности для:
- технических вопросов к ассистенту
- гипотетических рассуждений без личного опыта
- чужого опыта без личного контекста автора

Формат ответа:
{
  "entities": [
    {
      "type": "event",
      "confidence": 0.82,
      "title": "Краткое название",
      "fields": {
        "description": "Описание из диалога",
        "eventdate": "YYYY-MM-DD или null",
        "importance": 0.7
      }
    }
  ],
  "same_topic_as_pending": false,
  "updates": []
}

Цель (goal):
{
  "type": "goal",
  "confidence": 0.78,
  "title": "Название цели",
  "description": "Развёрнутое описание",
  "target_date": "YYYY-MM-DD или null",
  "priority": "low|medium|high"
}

Эксперимент (experiment):
{
  "type": "experiment",
  "confidence": 0.76,
  "title": "Название эксперимента",
  "description": "Что именно попробует",
  "hypothesis": "Ожидаемый результат"
}

Если в промпте указан pending-кандидат — оцени, относится ли новое сообщение к ТОМУ ЖЕ кандидату.
Если да — установи "same_topic_as_pending": true и повысь confidence.

Если ничего не обнаружено: {"entities": [], "same_topic_as_pending": false, "updates": []}
Верни ТОЛЬКО JSON."""


class DetectorAgent:
    """Background LLM agent for entity detection from chat messages."""

    def __init__(self, llm_service: Optional[LLMService] = None):
        self._llm = llm_service or LLMService()

    async def detect(
        self,
        thread_id: str,
        messages: List[Dict[str, Any]],
        context: DetectorContext,
    ) -> DetectorResult:
        if not messages:
            return DetectorResult()

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
            logger.error("[DetectorAgent] LLM call failed for thread %s: %s", thread_id, e)
            return DetectorResult()

        result = self._apply_session_filters(result, context.session_state)
        result = self._apply_context_rules(result, context)
        result = self._normalize_same_topic_flag(result, context.session_state)
        result = self._keep_top_chip_entity(result)

        return result

    def _normalize_same_topic_flag(
        self,
        result: DetectorResult,
        session_state: SessionState,
    ) -> DetectorResult:
        """Never treat different entity types as the same topic."""
        if not result.same_topic_as_pending or not session_state.active:
            return result
        for entity in result.entities:
            if entity.type != session_state.active.type:
                return result.model_copy(update={"same_topic_as_pending": False})
        return result

    def _build_prompt(
        self,
        messages: List[Dict[str, Any]],
        context: DetectorContext,
    ) -> str:
        lines: List[str] = []

        if context.is_event_context:
            lines.append(
                f"Чат привязан к существующей записи (ID: {context.entity_id}). "
                "НЕ предлагай новый event. Ищи goal, experiment или обогащение (updates)."
            )
        elif context.is_rhizome_context:
            lines.append(
                "Чат с главного экрана — будь внимательнее к event, goal и experiment."
            )
        else:
            lines.append("Свободный чат. Ищи event, goal и experiment.")

        active = context.session_state.active
        shelved = context.session_state.shelved
        if active:
            lines.append(
                f"\nАктивный кандидат (текущая тема):\n"
                f"- type: {active.type}\n"
                f"- title: {active.title}\n"
                f"- confidence: {active.confidence}\n"
                f"- fields: {json.dumps(active.fields, ensure_ascii=False)}\n"
                "Если новые сообщения про НЕГО — same_topic_as_pending: true."
            )
        if shelved:
            lines.append("\nПрипаркованные кандидаты (другая тема, можно вернуться):")
            for s in shelved[:5]:
                lines.append(
                    f"  - [{s.type}] {s.title} (confidence={s.confidence})"
                )
            lines.append(
                "Если пользователь снова говорит о припаркованной теме — "
                "same_topic_as_pending: true и укажи похожий title."
            )

        last_user_text = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_text = msg.get("content", "")
                break
        if last_user_text:
            lines.append(
                f"\n⚠️ ГЛАВНЫЙ ФОКУС — последнее сообщение пользователя:\n\"{last_user_text}\"\n"
                "Сущность определяй ПРЕЖДЕ ВСЕГО по этому сообщению. "
                "Если пользователь сменил тему (цель → событие или наоборот), "
                "верни новую сущность и same_topic_as_pending: false."
            )

        lines.append("\nПоследние сообщения диалога:")
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role == "user":
                lines.append(f"Пользователь: {content}")
            elif role == "assistant":
                lines.append(f"Ассистент: {content}")

        lines.append("\nПроанализируй диалог и верни JSON.")
        return "\n".join(lines)

    def _parse_llm_response(self, raw: str) -> DetectorResult:
        try:
            text = raw.strip()
            if text.startswith("```"):
                parts = text.split("```")
                text = parts[1] if len(parts) > 1 else text
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            data = json.loads(text)
            entities = [DetectedEntity(**e) for e in data.get("entities", [])]
            updates = [FieldUpdate(**u) for u in data.get("updates", [])]
            same_topic = bool(data.get("same_topic_as_pending", False))
            return DetectorResult(
                entities=entities,
                updates=updates,
                same_topic_as_pending=same_topic,
            )
        except Exception as e:
            logger.warning(
                "[DetectorAgent] Failed to parse LLM response: %s. Raw: %s",
                e,
                raw[:200],
            )
            return DetectorResult()

    def _apply_session_filters(
        self,
        result: DetectorResult,
        session_state: SessionState,
    ) -> DetectorResult:
        filtered = []
        for entity in result.entities:
            title = entity.title or entity.name or ""
            if session_state.is_declined(title):
                continue
            filtered.append(entity)
        return DetectorResult(
            entities=filtered,
            updates=result.updates,
            same_topic_as_pending=result.same_topic_as_pending,
        )

    def _apply_context_rules(
        self,
        result: DetectorResult,
        context: DetectorContext,
    ) -> DetectorResult:
        filtered = []
        for entity in result.entities:
            if entity.type == "event":
                if context.is_event_context:
                    continue
                threshold = (
                    _EVENT_THRESHOLD_RHIZOME
                    if context.is_rhizome_context
                    else _EVENT_THRESHOLD_FREE
                )
                if entity.confidence < threshold:
                    continue
            elif entity.type == "goal":
                if entity.confidence < _GOAL_THRESHOLD:
                    continue
            elif entity.type == "experiment":
                if entity.confidence < _EXPERIMENT_THRESHOLD:
                    continue
            elif entity.type == "concept":
                if entity.confidence < _CONCEPT_THRESHOLD_CHIP:
                    continue
            filtered.append(entity)

        return DetectorResult(
            entities=filtered,
            updates=result.updates,
            same_topic_as_pending=result.same_topic_as_pending,
        )

    def _keep_top_chip_entity(self, result: DetectorResult) -> DetectorResult:
        """Prefer event/goal/experiment with highest confidence."""
        chip = [e for e in result.entities if e.type in CHIP_ENTITY_TYPES]
        other = [e for e in result.entities if e.type not in CHIP_ENTITY_TYPES]
        if not chip:
            return result
        top = max(chip, key=lambda e: e.confidence)
        return DetectorResult(
            entities=[top] + other[:0],
            updates=result.updates,
            same_topic_as_pending=result.same_topic_as_pending,
        )
