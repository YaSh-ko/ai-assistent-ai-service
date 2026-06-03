from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.title_service import _fallback_title, _strip_leading_emoji, generate_title


def test_strip_leading_emoji_and_fallback():
    assert _strip_leading_emoji("🎯 Цель на год") == "Цель на год"
    assert _strip_leading_emoji("Цель на год") == "Цель на год"
    assert _fallback_title("") == "Новый чат"
    assert _fallback_title("one two three four five six") == "one two three four five"


@pytest.mark.asyncio
async def test_generate_title_success():
    llm = MagicMock()
    llm.generate_response = AsyncMock(return_value=MagicMock(content="Короткий заголовок"))

    title = await generate_title("Сообщение пользователя", llm)

    assert title == "Короткий заголовок"
    assert "💬" not in title
    llm.generate_response.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_title_strips_llm_emoji_prefix():
    llm = MagicMock()
    llm.generate_response = AsyncMock(return_value=MagicMock(content="🎯 Цель на год"))

    title = await generate_title("Сообщение", llm)

    assert title == "Цель на год"


@pytest.mark.asyncio
async def test_generate_title_fallback_on_error():
    llm = MagicMock()
    llm.generate_response = AsyncMock(side_effect=RuntimeError("boom"))

    title = await generate_title("Нужен новый заголовок", llm)

    assert "💬" not in title
    assert "Нужен новый заголовок" in title
