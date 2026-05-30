"""
AI-powered insights: day summaries, cluster analysis, goal task suggestions.
"""
import json
import logging
import re
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_llm_service
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["insights"])

TaskPhase = Literal["now", "next", "backlog"]


class EntityItem(BaseModel):
    id: str
    type: str
    title: str
    description: str = ""
    status: str = ""
    created_at: str = ""


class SummarizeRequest(BaseModel):
    entities: List[EntityItem]
    context: str = Field(description="day_summary | week_summary | cluster_analysis")
    date: Optional[str] = None
    week_end: Optional[str] = None


class SummarizeResponse(BaseModel):
    summary: str


_DAY_SYSTEM = """Ты — аналитик личного дневника развития. Пользователь ведёт наблюдения, ставит цели и создаёт задачи.
Тебе дан список сущностей за один день. Напиши краткую, тёплую сводку дня на русском языке:
- Что произошло (ключевые события/наблюдения)
- Прогресс по целям (если есть)
- Настроение и энергия (если можно определить из текста)
- Один совет или мысль на завтра

Пиши кратко (3-6 предложений), без заголовков и списков. Обращайся на «ты»."""

_WEEK_SYSTEM = """Ты — аналитик личного дневника развития. Пользователь ведёт наблюдения, ставит цели и создаёт задачи.
Тебе дан список сущностей за одну неделю. Напиши аналитическую сводку на русском языке:
- Главные темы и повторяющиеся паттерны недели
- Прогресс по целям и выполненным задачам
- Динамика настроения и энергии (если видна из наблюдений)
- Что получилось хорошо и где были сложности
- 1–2 конкретных фокуса на следующую неделю

Пиши связным текстом (5-8 предложений), без заголовков и маркированных списков. Обращайся на «ты»."""

_CLUSTER_SYSTEM = """Ты — аналитик личного дневника развития. Тебе дан кластер связанных сущностей пользователя (наблюдения, цели, задачи), объединённых общей темой.

Проанализируй этот кластер и напиши на русском:
- Общая тема этого кластера (1 предложение)
- Какой прогресс виден (что уже сделано, что в процессе)
- Тренды и закономерности (что повторяется, что растёт/падает)
- Одна конкретная рекомендация

Пиши кратко (4-7 предложений), без заголовков и маркированных списков. Обращайся на «ты»."""


def _build_entities_block(
    entities: list[EntityItem],
    date: str | None = None,
    week_end: str | None = None,
) -> str:
    if date and week_end:
        header = f"Период недели: {date} — {week_end}\n\n"
    elif date:
        header = f"Дата: {date}\n\n"
    else:
        header = ""
    lines = []
    for e in entities:
        status_part = f" [{e.status}]" if e.status else ""
        lines.append(f"- [{e.type}]{status_part} «{e.title}»: {e.description[:200]}")
    return header + "\n".join(lines)


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize_entities(
    request: SummarizeRequest,
    llm: LLMService = Depends(get_llm_service),
) -> SummarizeResponse:
    """Generate an AI summary for a set of entities."""
    if not request.entities:
        return SummarizeResponse(summary="Нет данных для анализа.")

    if request.context == "day_summary":
        system = _DAY_SYSTEM
    elif request.context == "week_summary":
        system = _WEEK_SYSTEM
    else:
        system = _CLUSTER_SYSTEM

    user_prompt = _build_entities_block(request.entities, request.date, request.week_end)

    logger.info(
        "[Insights] Generating %s for %d entities",
        request.context, len(request.entities),
    )

    try:
        response = await llm.generate_response(
            prompt=user_prompt,
            model_name="gigachat",
            system_prompt=system,
            max_tokens=700 if request.context == "week_summary" else 500,
            temperature=0.7,
        )
        summary = response.content if hasattr(response, "content") else str(response)
        logger.info("[Insights] Summary generated: %d chars", len(summary))
        return SummarizeResponse(summary=summary)
    except Exception as e:
        logger.error("[Insights] LLM generation failed: %s", e, exc_info=True)
        return SummarizeResponse(summary="Не удалось сгенерировать сводку. Попробуйте позже.")


class ExistingTaskItem(BaseModel):
    title: str
    status: str = ""
    phase: str = ""


class SuggestGoalTasksRequest(BaseModel):
    title: str
    description: str = ""
    priority: Optional[str] = None
    target_date: Optional[str] = None
    existing_tasks: List[ExistingTaskItem] = Field(default_factory=list)


class SuggestedTaskItem(BaseModel):
    title: str
    phase: TaskPhase = "now"
    description: Optional[str] = None


class SuggestGoalTasksResponse(BaseModel):
    tasks: List[SuggestedTaskItem]


_GOAL_TASKS_SYSTEM = """Ты — коуч по личному развитию. Разбей цель на шаги, которые можно однозначно отметить «сделано».

Верни ТОЛЬКО JSON без markdown:
{
  "tasks": [
    {"title": "...", "phase": "now", "description": "..."},
    ...
  ]
}

Критерий хорошего шага (title):
- Одно конкретное действие: что именно сделать, в каком объёме
- Выполнимо за одну сессию (15–90 мин) или за 1–3 дня максимум
- В title есть глагол и измеримый результат («написать 3 абзаца», «отправить 2 письма», «пройти урок 1»)
- Понятно, когда шаг завершён — без «улучшить», «заниматься», «работать над», «составить план», «подумать о»

Плохо → хорошо:
- «Составить план обучения» → «Выбрать один курс и записаться на пробный урок до пятницы»
- «Работать над проектом» → «Сверстать главную страницу в Figma (1 экран)»
- «Улучшить здоровье» → «Записаться к терапевту через приложение клиники»

Правила:
- 4–6 шагов, русский язык
- phase: "now" (эта неделя), "next" (следующий этап), "backlog" (позже, без срока)
- description — опционально: критерий «готово» в одном предложении
- Не дублируй существующие задачи пользователя
- Каждый шаг привязан к формулировке цели"""

_VAGUE_TASK_RE = re.compile(
    r"(составить план|наметить|подумать|улучшить|развивать|работать над|"
    r"заниматься|продолжить работу|больше внимания|в целом|в перспективе|"
    r"при необходимости|по возможности)",
    re.IGNORECASE,
)


def _is_actionable_title(title: str) -> bool:
    t = title.strip()
    if len(t) < 15:
        return False
    if _VAGUE_TASK_RE.search(t):
        return False
    return True


def _strip_json_fence(text: str) -> str:
    raw = text.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def _normalize_phase(value: str) -> TaskPhase:
    phase = (value or "now").lower().strip()
    if phase in ("now", "next", "backlog"):
        return phase  # type: ignore[return-value]
    return "now"


def _parse_suggested_tasks(raw: str) -> List[SuggestedTaskItem]:
    text = _strip_json_fence(raw)
    data = json.loads(text)
    items = data.get("tasks", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []

    result: List[SuggestedTaskItem] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        if not title or not _is_actionable_title(title):
            continue
        result.append(
            SuggestedTaskItem(
                title=title[:200],
                phase=_normalize_phase(str(item.get("phase", "now"))),
                description=(str(item.get("description", "")).strip()[:300] or None),
            )
        )
    return result[:8]


def _fallback_tasks(title: str) -> List[SuggestedTaskItem]:
    short = title[:40] + ("…" if len(title) > 40 else "")
    return [
        SuggestedTaskItem(
            title=f"Записать критерий «готово» для «{short}» в одном предложении",
            phase="now",
            description="Поймёшь, когда цель достигнута",
        ),
        SuggestedTaskItem(
            title="Заблокировать 45 минут в календаре на первый шаг на этой неделе",
            phase="now",
        ),
        SuggestedTaskItem(
            title="Сделать один минимальный шаг сегодня (до 30 мин) и зафиксировать результат",
            phase="now",
        ),
        SuggestedTaskItem(
            title="Собрать список из 3 препятствий и одного способа обойти каждое",
            phase="next",
        ),
        SuggestedTaskItem(
            title="Сохранить 2–3 идеи «на потом» в бэклог без срока",
            phase="backlog",
        ),
    ]


def _build_goal_tasks_prompt(request: SuggestGoalTasksRequest) -> str:
    lines = [
        f"Цель: {request.title}",
        f"Описание: {request.description or '—'}",
    ]
    if request.priority:
        lines.append(f"Приоритет: {request.priority}")
    if request.target_date:
        lines.append(f"Дедлайн: {request.target_date}")
    if request.existing_tasks:
        lines.append("\nУже есть задачи (не повторяй):")
        for t in request.existing_tasks:
            status = f" [{t.status}]" if t.status else ""
            phase = f" ({t.phase})" if t.phase else ""
            lines.append(f"- {t.title}{status}{phase}")
    lines.append(
        "\nПредложи 4–6 шагов в JSON. Каждый title — одно конкретное действие с измеримым результатом."
    )
    return "\n".join(lines)


@router.post("/suggest-goal-tasks", response_model=SuggestGoalTasksResponse)
async def suggest_goal_tasks(
    request: SuggestGoalTasksRequest,
    llm: LLMService = Depends(get_llm_service),
) -> SuggestGoalTasksResponse:
    """Suggest actionable tasks for a personal goal."""
    if not request.title.strip():
        return SuggestGoalTasksResponse(tasks=[])

    user_prompt = _build_goal_tasks_prompt(request)
    logger.info("[Insights] Suggesting tasks for goal: %s", request.title[:80])

    try:
        response = await llm.generate_response(
            prompt=user_prompt,
            model_name="gigachat",
            system_prompt=_GOAL_TASKS_SYSTEM,
            max_tokens=800,
            temperature=0.35,
        )
        raw = response.content if hasattr(response, "content") else str(response)
        tasks = _parse_suggested_tasks(raw)
        if tasks:
            logger.info("[Insights] Parsed %d suggested tasks", len(tasks))
            return SuggestGoalTasksResponse(tasks=tasks)
        logger.warning("[Insights] Empty task list from LLM, using fallback")
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("[Insights] Failed to parse goal tasks JSON: %s", e)
    except Exception as e:
        logger.error("[Insights] Goal tasks LLM failed: %s", e, exc_info=True)

    return SuggestGoalTasksResponse(tasks=_fallback_tasks(request.title))
