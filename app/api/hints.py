"""
Hints API — динамические подсказки для чата.

POST /api/v1/hints
Принимает последние сообщения диалога (или пустой список),
возвращает 3 коротких вопроса-подсказки, сгенерированных LLM.
"""

import asyncio
import logging
from typing import Annotated, Any, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_llm_service
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hints", tags=["hints"])

# Статических подсказки — fallback при ошибке LLM
_FALLBACK_HINTS = [
    "Как я себя чувствую сегодня?",
    "Что меня больше всего занимает сейчас?",
    "Что я хочу изменить в своей жизни?",
]

_INITIAL_PROMPT = """Ты — помощник-дневник Delёz. Сгенерируй ровно 3 коротких вопроса (каждый не длиннее 60 символов), которые помогут пользователю начать разговор с собой. Вопросы должны быть разными по теме — о чувствах, о целях, о событиях. Отвечай ТОЛЬКО списком из 3 строк, по одной на каждую строку, без нумерации и без лишних слов."""

_CONTEXT_PROMPT = """Ты — помощник-дневник Delёz. На основе следующего диалога сгенерируй ровно 3 коротких вопроса (каждый не длиннее 60 символов), которые помогут пользователю продолжить разговор с собой — углубиться в тему, посмотреть под другим углом или задуматься о следующем шаге. Отвечай ТОЛЬКО списком из 3 строк, по одной на каждую строку, без нумерации и без лишних слов.

Диалог:
{dialogue}"""


def _format_dialogue(messages: List[dict]) -> str:
    """Форматирует последние сообщения для вставки в промпт."""
    lines = []
    for msg in messages:
        role = msg.get("type", msg.get("role", ""))
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        if role in ("human", "user"):
            lines.append(f"Пользователь: {content}")
        elif role in ("ai", "assistant"):
            lines.append(f"Delёz: {content}")
    return "\n".join(lines)


def _parse_hints(raw: str) -> List[str]:
    """Извлекает ровно 3 строки из ответа LLM."""
    lines = [line.strip().lstrip("-•*0123456789.) ") for line in raw.strip().splitlines()]
    lines = [l for l in lines if l]
    if len(lines) >= 3:
        return lines[:3]
    # Если LLM вернул меньше строк, дополняем fallback-подсказками
    while len(lines) < 3:
        lines.append(_FALLBACK_HINTS[len(lines)])
    return lines


class HintsRequest(BaseModel):
    """Запрос подсказок."""
    messages: Optional[List[dict]] = None  # последние сообщения диалога (до 6)


class HintsResponse(BaseModel):
    """Ответ с подсказками."""
    hints: List[str]


@router.post("", response_model=HintsResponse)
async def get_hints(
    request: HintsRequest,
    llm_service: Annotated[LLMService, Depends(get_llm_service)],
) -> HintsResponse:
    """
    Генерирует 3 динамических вопроса-подсказки через LLM.

    - Если messages пустой или отсутствует → общие вопросы для старта диалога.
    - Если messages заполнен → контекстные вопросы на основе диалога.
    - При любой ошибке LLM → возвращает статический fallback.
    """
    messages = request.messages or []
    # Берём не более 6 последних сообщений для экономии токенов
    recent = messages[-6:] if len(messages) > 6 else messages

    try:
        if recent:
            dialogue = _format_dialogue(recent)
            prompt = _CONTEXT_PROMPT.format(dialogue=dialogue)
        else:
            prompt = _INITIAL_PROMPT

        raw = await asyncio.wait_for(
            llm_service.generate(prompt, task_type="simple_question"),
            timeout=10.0,
        )
        hints = _parse_hints(raw)
        return HintsResponse(hints=hints)

    except asyncio.TimeoutError:
        logger.warning("Hints generation timed out, using fallback")
        return HintsResponse(hints=_FALLBACK_HINTS)
    except Exception as e:
        logger.error(f"Hints generation failed: {e}")
        return HintsResponse(hints=_FALLBACK_HINTS)
