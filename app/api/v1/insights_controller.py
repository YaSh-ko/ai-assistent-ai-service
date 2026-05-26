"""
AI-powered insights: day summaries and cluster analysis.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_llm_service
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["insights"])


class EntityItem(BaseModel):
    id: str
    type: str
    title: str
    description: str = ""
    status: str = ""
    created_at: str = ""


class SummarizeRequest(BaseModel):
    entities: List[EntityItem]
    context: str = Field(description="day_summary | cluster_analysis")
    date: Optional[str] = None


class SummarizeResponse(BaseModel):
    summary: str


_DAY_SYSTEM = """Ты — аналитик личного дневника развития. Пользователь ведёт наблюдения, ставит цели и создаёт задачи.
Тебе дан список сущностей за один день. Напиши краткую, тёплую сводку дня на русском языке:
- Что произошло (ключевые события/наблюдения)
- Прогресс по целям (если есть)
- Настроение и энергия (если можно определить из текста)
- Один совет или мысль на завтра

Пиши кратко (3-6 предложений), без заголовков и списков. Обращайся на «ты»."""

_CLUSTER_SYSTEM = """Ты — аналитик личного дневника развития. Тебе дан кластер связанных сущностей пользователя (наблюдения, цели, задачи), объединённых общей темой.

Проанализируй этот кластер и напиши на русском:
- Общая тема этого кластера (1 предложение)
- Какой прогресс виден (что уже сделано, что в процессе)
- Тренды и закономерности (что повторяется, что растёт/падает)
- Одна конкретная рекомендация

Пиши кратко (4-7 предложений), без заголовков и маркированных списков. Обращайся на «ты»."""


def _build_entities_block(entities: list[EntityItem], date: str | None = None) -> str:
    header = f"Дата: {date}\n\n" if date else ""
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
    else:
        system = _CLUSTER_SYSTEM

    user_prompt = _build_entities_block(request.entities, request.date)

    logger.info(
        "[Insights] Generating %s for %d entities",
        request.context, len(request.entities),
    )

    try:
        response = await llm.generate_response(
            prompt=user_prompt,
            model_name="gigachat",
            system_prompt=system,
            max_tokens=500,
            temperature=0.7,
        )
        summary = response.content if hasattr(response, "content") else str(response)
        logger.info("[Insights] Summary generated: %d chars", len(summary))
        return SummarizeResponse(summary=summary)
    except Exception as e:
        logger.error("[Insights] LLM generation failed: %s", e, exc_info=True)
        return SummarizeResponse(summary="Не удалось сгенерировать сводку. Попробуйте позже.")
