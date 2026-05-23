"""
TitleService — generates a short emoji-prefixed chat title from the first user message using LLM.
Fire-and-forget safe: never raises, always returns a non-empty string.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = "Ты помощник, который придумывает короткие названия для чатов."

_PROMPT_TEMPLATE = (
    "Придумай название для чата (2-4 слова) и подбери один подходящий эмодзи.\n"
    "Формат ответа строго: [эмодзи] [название]. Пример: 🎯 Цель на год\n"
    "Только эмодзи и название, без кавычек и пояснений.\n\n"
    "Сообщение: {user_message}"
)

_DEFAULT_EMOJI = "💬"


def _starts_with_emoji(s: str) -> bool:
    """Check if string starts with an emoji character."""
    if not s:
        return False
    cp = ord(s[0])
    return (
        0x1F300 <= cp <= 0x1FAFF  # Misc symbols, emoticons, transport, etc.
        or 0x2600 <= cp <= 0x27BF  # Misc symbols and dingbats
        or 0xFE00 <= cp <= 0xFE0F  # Variation selectors
    )


def _fallback_title(user_message: str) -> str:
    """Return emoji + first 5 words of the message, or default if empty."""
    words = user_message.split()
    if not words:
        return f"{_DEFAULT_EMOJI} Новый чат"
    return f"{_DEFAULT_EMOJI} {' '.join(words[:5])}"


async def generate_title(user_message: str, llm_service: Any) -> str:
    """
    Generate a short emoji-prefixed chat title (2-4 words) via LLM.

    - Uses gigachat (same model as simple user queries).
    - Uses max_tokens=20 and temperature=0.3 to keep it fast and deterministic.
    - Prepends '💬 ' if LLM response doesn't start with an emoji.
    - Falls back to '💬 <first 5 words>' on any error or empty response.
    - Never raises an exception.
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
        title = (response.content or "").strip()
        if not title:
            raise ValueError("LLM returned empty title")
        # Ensure title starts with an emoji
        if not _starts_with_emoji(title):
            title = f"{_DEFAULT_EMOJI} {title}"
        return title
    except Exception as e:
        logger.warning("Title generation via LLM failed, using fallback: %s", e)
        return _fallback_title(user_message)
