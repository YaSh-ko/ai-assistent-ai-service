import importlib
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest


def _import_runs_module():
    fake_deps = types.ModuleType("app.api.deps")
    fake_deps.get_rag_chain = lambda: None
    fake_deps.get_session_manager = lambda: None
    sys.modules["app.api.deps"] = fake_deps
    sys.modules.pop("app.api.runs", None)
    return importlib.import_module("app.api.runs")


def test_parse_checkpoint_and_merge_messages():
    module = _import_runs_module()
    req = module.RunStreamRequest(checkpoint={"checkpoint_id": "cp-1"})
    assert module._parse_checkpoint_id(req) == "cp-1"

    merged = module._merge_normal_messages(
        existing_messages=[{"id": "1", "type": "human", "content": "a"}],
        input_data={"messages": [{"id": "1", "type": "human", "content": "a"}, {"id": "2", "type": "ai", "content": "b"}]},
    )
    assert [m["id"] for m in merged] == ["1", "2"]


@pytest.mark.asyncio
async def test_handle_regeneration_flow_trims_to_last_human():
    module = _import_runs_module()
    session_manager = MagicMock()
    session_manager.get_messages_by_checkpoint = AsyncMock(
        return_value=[
            {"type": "human", "content": "first"},
            {"type": "ai", "content": "answer"},
            {"type": "human", "content": "second"},
            {"type": "ai", "content": "tail"},
        ]
    )

    user_message, history = await module._handle_regeneration_flow(
        thread_id="t-1",
        checkpoint_id="cp-1",
        existing_messages=[],
        session_manager=session_manager,
    )

    assert user_message == "second"
    assert history[-1]["type"] == "human"

