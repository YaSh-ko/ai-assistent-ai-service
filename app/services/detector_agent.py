"""
Detector Agent — background LLM agent that detects entities (events, goals, experiments)
from chat messages and returns structured results.
"""
import json
import logging
import re
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
_OBSERVATION_THRESHOLD_FREE = 0.55
_OBSERVATION_THRESHOLD_RHIZOME = 0.50
_GOAL_THRESHOLD = 0.55
_TASK_THRESHOLD = 0.55
MAX_RESULTS = 5

_SYSTEM_PROMPT = """Ты — аналитический агент системы Delёz (бортовой журнал развития).
Анализируй диалог и определяй, есть ли кандидаты на создание структурированных сущностей.

Верни ТОЛЬКО валидный JSON без пояснений.

Типы сущностей:
1. observation — наблюдение, мысль, осознание, факт или событие из жизни пользователя.
   Что-то, что он заметил, пережил, понял. Не гипотеза, а факт/наблюдение.
2. goal — конкретная цель. Что пользователь хочет достичь, к какому сроку, как поймёт что достиг.
   Помни: хорошая цель конкретна и измерима.
3. task — один конкретный шаг к цели.
   Выполним за одну сессию (до 90 мин) или 1–3 дня. В title — глагол + измеримый результат.
   Примеры: «Отправить 2 письма менторам», «Пройти урок 1 и конспект на 5 пунктов».
   НЕ предлагай: «составить план», «работать над», «улучшить», «заниматься».

НЕ создавай сущности для:
- технических вопросов к ассистенту
- гипотетических рассуждений без конкретики
- чужого опыта без личного контекста автора
- абстрактных размышлений без намерения действовать

Формат ответа — Наблюдение (observation):
{
  "entities": [
    {
      "type": "observation",
      "confidence": 0.82,
      "title": "Краткое название (3-7 слов)",
      "fields": {
        "description": "Развёрнутое описание из контекста диалога (2-4 предложения)",
        "event_date": "YYYY-MM-DD или null (дата когда произошло/замечено)",
        "area": "область жизни: career|health|skills|relationships|finance|personal|other"
      }
    }
  ],
  "same_topic_as_pending": false,
  "updates": []
}

Формат — Цель (goal):
{
  "type": "goal",
  "confidence": 0.78,
  "title": "Название цели (конкретное, 3-8 слов)",
  "fields": {
    "description": "Что именно хочет достичь и как поймёт что достиг (2-4 предложения)",
    "target_date": "YYYY-MM-DD или null",
    "priority": "low|medium|high",
    "measurable": "Как измерить результат (1 предложение)",
    "area": "career|health|skills|relationships|finance|personal|other"
  }
}

Формат — Задача (task):
{
  "type": "task",
  "confidence": 0.76,
  "title": "Одно действие с измеримым результатом (5-12 слов)",
  "fields": {
    "description": "Критерий «готово» — когда шаг считается выполненным (1-2 предложения)",
    "deadline": "YYYY-MM-DD или null (когда нужно выполнить)",
    "area": "career|health|skills|relationships|finance|personal|other"
  }
}

Если в промпте указан pending-кандидат — оцени, относится ли новое сообщение к ТОМУ ЖЕ кандидату.
Если да — установи "same_topic_as_pending": true и повысь confidence.

Если тема совпадает с СУЩЕСТВУЮЩЕЙ сущностью пользователя (они будут перечислены в промпте),
верни action: "update" и existing_entity_id вместо создания дубликата.
Пример update:
{
  "type": "goal", "confidence": 0.85, "action": "update",
  "existing_entity_id": "uuid-of-existing-goal",
  "title": "Исходное название цели",
  "fields": {"description": "Дополненное описание с новой информацией из диалога"}
}

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
        existing_entities: Optional[List[Dict[str, Any]]] = None,
    ) -> DetectorResult:
        if not messages:
            return DetectorResult()

        recent = messages[-10:]
        prompt = self._build_prompt(recent, context, existing_entities=existing_entities)

        logger.info(
            "[DetectorAgent] === Detect start === thread=%s msgs=%d existing_entities=%d",
            thread_id, len(recent), len(existing_entities) if existing_entities else 0,
        )
        logger.debug("[DetectorAgent] Full prompt (%d chars):\n%s", len(prompt), prompt[:2000])

        try:
            raw = await self._llm.generate(
                prompt=prompt,
                task_type="simple_question",
                system_prompt=_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=1024,
            )
            logger.info("[DetectorAgent] LLM raw response (%d chars): %s", len(raw), raw[:500])
            result = self._parse_llm_response(raw)
        except Exception as e:
            logger.error("[DetectorAgent] LLM call failed for thread %s: %s", thread_id, e, exc_info=True)
            return DetectorResult()

        if result.entities:
            for i, ent in enumerate(result.entities):
                logger.info(
                    "[DetectorAgent] Parsed entity #%d: type=%s action=%s conf=%.2f title=%r existing_id=%s fields=%s",
                    i + 1, ent.type, ent.action, ent.confidence, ent.title,
                    ent.existing_entity_id, list((ent.fields or {}).keys()),
                )
        else:
            logger.info("[DetectorAgent] LLM returned no entities")

        result = self._sanitize_update_actions(result, existing_entities)

        pre_filter_count = len(result.entities)
        result = self._apply_session_filters(result, context.session_state)
        if len(result.entities) < pre_filter_count:
            logger.info(
                "[DetectorAgent] Session filter removed %d entities (declined)",
                pre_filter_count - len(result.entities),
            )

        pre_ctx_count = len(result.entities)
        result = self._apply_context_rules(result, context)
        if len(result.entities) < pre_ctx_count:
            logger.info(
                "[DetectorAgent] Context rules removed %d entities (threshold/type)",
                pre_ctx_count - len(result.entities),
            )

        result = self._normalize_same_topic_flag(result, context.session_state)
        result = self._keep_top_chip_entity(result)

        logger.info(
            "[DetectorAgent] === Detect done === thread=%s final_entities=%d same_topic=%s",
            thread_id, len(result.entities), result.same_topic_as_pending,
        )
        return result

    _UUID_RE = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )

    def _sanitize_update_actions(
        self,
        result: DetectorResult,
        existing_entities: Optional[List[Dict[str, Any]]],
    ) -> DetectorResult:
        """
        Prevent LLM hallucinations: if no existing entities were provided,
        or the returned existing_entity_id is not a valid UUID,
        force action back to 'create'.
        """
        valid_map: Dict[str, str] = {}
        if existing_entities:
            for e in existing_entities:
                eid = e.get("entity_id", "")
                if eid and self._UUID_RE.match(eid):
                    valid_map[eid] = e.get("title", "")

        changed = False
        sanitized = []
        for ent in result.entities:
            if ent.action == "update":
                eid = ent.existing_entity_id or ""
                if not self._UUID_RE.match(eid) or eid not in valid_map:
                    logger.warning(
                        "[DetectorAgent] Sanitized hallucinated update: existing_id=%r → forced to create",
                        eid[:60],
                    )
                    ent = ent.model_copy(update={"action": "create", "existing_entity_id": None, "existing_title": None})
                    changed = True
                else:
                    real_title = valid_map[eid]
                    if real_title and ent.existing_title != real_title:
                        ent = ent.model_copy(update={"existing_title": real_title})
                        changed = True
            sanitized.append(ent)

        if changed:
            return result.model_copy(update={"entities": sanitized})
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
        existing_entities: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        lines: List[str] = []

        if context.is_goal_context:
            tc = context.thread_context or {}
            lines.append(
                f"Чат привязан к цели (ID: {context.entity_id}). "
                "Это приоритетный контекст — 100% сообщений относятся к этой цели."
            )
            lines.append(f"Цель: «{tc.get('title', '')}»")
            if tc.get("description"):
                lines.append(f"Описание цели: {tc.get('description')}")
            if tc.get("target_date"):
                lines.append(f"Дедлайн цели: {tc.get('target_date')}")
            existing_tasks = tc.get("existing_tasks") or []
            if existing_tasks:
                lines.append("Уже есть шаги (не дублируй):")
                for t in existing_tasks[:15]:
                    lines.append(f"  - {t}")
            lines.append(
                "Правила:\n"
                "- Новые шаги → type task, action create (конкретное действие).\n"
                "- Уточнение цели (описание, срок, приоритет) → type goal, action update, "
                f"existing_entity_id: {context.entity_id}.\n"
                "- НЕ создавай новую goal.\n"
                "- Не предлагай observation, если пользователь не описывает отдельное жизненное событие."
            )
        elif context.is_event_context:
            lines.append(
                f"Чат привязан к существующему наблюдению (ID: {context.entity_id}). "
                "НЕ предлагай новое observation. Ищи goal, task или обогащение (updates)."
            )
        elif context.is_rhizome_context:
            lines.append(
                "Чат с главного экрана — ищи observation, goal и task."
            )
        else:
            lines.append(
                "Свободный чат. Ищи observation и goal. "
                "Не предлагай task без привязки к цели — шаги планируются в чате конкретной цели."
            )

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

        if existing_entities:
            lines.append(
                "\n## Существующие сущности пользователя (найдены по смыслу):\n"
                "Если тема диалога совпадает с одной из них — верни action: \"update\" "
                "и existing_entity_id. НЕ создавай дубликат."
            )
            for ent in existing_entities[:MAX_RESULTS]:
                etype = ent.get("entity_type", "?")
                eid = ent.get("entity_id", "?")
                etitle = ent.get("title", "")
                edesc = ent.get("description", "")[:120]
                estatus = ent.get("status", "")
                lines.append(
                    f"  - [{etype}] id={eid} «{etitle}» status={estatus} | {edesc}"
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
            if entity.type == "observation":
                if context.is_event_context:
                    continue
                threshold = (
                    _OBSERVATION_THRESHOLD_RHIZOME
                    if context.is_rhizome_context
                    else _OBSERVATION_THRESHOLD_FREE
                )
                if entity.confidence < threshold:
                    continue
            elif entity.type == "goal":
                if entity.confidence < _GOAL_THRESHOLD:
                    continue
            elif entity.type == "task":
                if entity.confidence < _TASK_THRESHOLD:
                    continue
            else:
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
