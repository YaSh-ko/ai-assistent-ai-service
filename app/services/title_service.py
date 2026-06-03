"""
TitleService — generates a short chat title from the first user message using LLM.
Fire-and-forget safe: never raises, always returns a non-empty string.
"""
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = "Ты помощник, который придумывает короткие названия для чатов."

_PROMPT_TEMPLATE = (
    "Придумай название для чата (2-4 слова).\n"
    "Формат ответа строго: только название. Пример: Цель на год\n"
    "Только название, без кавычек и пояснений.\n\n"
    "Сообщение: {user_message}"
)

# Leading emoji prefix if the model still returns the old format
_LEADING_EMOJI = re.compile(
    r"^(?:["
    r"\U0001F300-\U0001FAFF"
    r"\U00002600-\U000027BF"
    r"\U0000FE00-\U0000FE0F"
    r"]+\s*)+",
    flags=re.UNICODE,
)

_DEFAULT_TITLE = "Новый чат"


def _strip_leading_emoji(title: str) -> str:
    """Drop a leading emoji cluster (old LLM habit), keep the title as returned."""
    return _LEADING_EMOJI.sub("", title).strip()


def _fallback_title(user_message: str) -> str:
    """First 5 words of the message, or default if empty."""
    words = user_message.split()
    if not words:
        return _DEFAULT_TITLE
    return " ".join(words[:5])


async def generate_title(user_message: str, llm_service: Any) -> str:
    """
    Generate a short chat title (2-4 words) via LLM.

    Same flow as before, but without prepending an emoji to the title.
    """
    try:
        prompt = _PROMPT_TEMPLATE.format(user_message=user_message)
        response = await llm_service.generate_response(
            prompt=prompt,
            model_name="gigachat",
            system_prompt=_SYSTEM_PROMPT,
            max_tokens=20,
            temperature=0.3,
        )
        title = _strip_leading_emoji((response.content or "").strip().strip("\"'«»"))
        if not title:
            raise ValueError("LLM returned empty title")
        return title[:80]
    except Exception as e:
        logger.warning("Title generation via LLM failed, using fallback: %s", e)
        return _fallback_title(user_message)
