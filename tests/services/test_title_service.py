from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.title_service import _fallback_title, _starts_with_emoji, generate_title


def test_starts_with_emoji_and_fallback():
    assert _starts_with_emoji("🎯 Цель")
    assert not _starts_with_emoji("Goal")
    assert _fallback_title("") == "💬 Новый чат"
    assert _fallback_title("one two three four five six") == "💬 one two three four five"


@pytest.mark.asyncio
async def test_generate_title_success_and_prefix():
    llm = MagicMock()
    llm.generate_response = AsyncMock(return_value=MagicMock(content="Короткий заголовок"))

    title = await generate_title("Сообщение пользователя", llm)

    assert title == "💬 Короткий заголовок"
    llm.generate_response.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_title_fallback_on_error():
    llm = MagicMock()
    llm.generate_response = AsyncMock(side_effect=RuntimeError("boom"))

    title = await generate_title("Нужен новый заголовок", llm)

    assert title.startswith("💬 ")
    assert "Нужен новый заголовок" in title

