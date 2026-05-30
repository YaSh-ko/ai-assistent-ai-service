import asyncio
import importlib
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest


def _import_hints_module():
    fake_deps = types.ModuleType("app.api.deps")
    fake_deps.get_llm_service = lambda: None
    sys.modules["app.api.deps"] = fake_deps
    sys.modules.pop("app.api.hints", None)
    return importlib.import_module("app.api.hints")


def test_format_dialogue_and_parse_hints():
    module = _import_hints_module()
    dialogue = module._format_dialogue(
        [
            {"type": "human", "content": "Привет"},
            {"type": "ai", "content": [{"type": "text", "text": "Ответ"}]},
            {"role": "user", "content": "Еще вопрос"},
        ]
    )
    assert "Пользователь: Привет" in dialogue
    assert "Impulse: Ответ" in dialogue

    parsed = module._parse_hints("1) Первый\n- Второй")
    assert len(parsed) == 3
    assert parsed[0] == "Первый"


@pytest.mark.asyncio
async def test_get_hints_success_and_fallbacks():
    module = _import_hints_module()
    llm = MagicMock()
    llm.generate = AsyncMock(return_value="Q1\nQ2\nQ3")
    result = await module.get_hints(module.HintsRequest(messages=[{"type": "human", "content": "hi"}]), llm)
    assert result.hints == ["Q1", "Q2", "Q3"]

    llm.generate = AsyncMock(side_effect=asyncio.TimeoutError())
    timeout_result = await module.get_hints(module.HintsRequest(messages=[]), llm)
    assert len(timeout_result.hints) == 3

    llm.generate = AsyncMock(side_effect=RuntimeError("boom"))
    error_result = await module.get_hints(module.HintsRequest(messages=[]), llm)
    assert len(error_result.hints) == 3

