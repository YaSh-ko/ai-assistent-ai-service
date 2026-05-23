import importlib
import sys
import types
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException


def _import_threads_module():
    fake_deps = types.ModuleType("app.api.deps")
    fake_deps.get_session_manager = lambda: None
    sys.modules["app.api.deps"] = fake_deps
    sys.modules.pop("app.api.threads", None)
    return importlib.import_module("app.api.threads")


def _session(thread_id: str = "t-1", states=None, history=None):
    return MagicMock(
        thread_id=thread_id,
        created_at=datetime(2026, 1, 1),
        metadata={"k": "v"},
        states=states or [],
        history=history or [],
    )


@pytest.mark.asyncio
async def test_create_thread_existing_and_update_delete_flow():
    module = _import_threads_module()
    manager = MagicMock()
    manager.get_session = AsyncMock(return_value=_session("t-1"))
    manager.create_session = AsyncMock(return_value=_session("t-2"))
    manager.update_session = AsyncMock(return_value=_session("t-1"))
    manager.repository.delete = AsyncMock(return_value=True)
    manager._cache = {"t-1": object()}

    existing = await module.create_thread(module.ThreadCreateRequest(thread_id="t-1"), manager, None)
    assert existing.thread_id == "t-1"

    created = await module.create_thread(module.ThreadCreateRequest(), manager, "u-1")
    assert created.thread_id == "t-2"

    updated = await module.update_thread("t-1", {"title": "New", "metadata": {"x": 1}}, manager)
    assert updated.thread_id == "t-1"

    deleted = await module.delete_thread("t-1", manager)
    assert deleted == {"status": "ok"}


@pytest.mark.asyncio
async def test_threads_state_and_history_fallbacks_and_not_found():
    module = _import_threads_module()
    manager = MagicMock()
    manager._cache = {}
    manager.get_session = AsyncMock(side_effect=[None, _session(states=[], history=[{"type": "human"}]), _session(states=[{"checkpoint": {"checkpoint_id": "cp"}}])])

    with pytest.raises(HTTPException):
        await module.get_thread("missing", manager)

    state = await module.get_thread_state("t-1", manager)
    assert state["values"]["messages"] == [{"type": "human"}]

    history = await module.get_thread_history("t-1", module.ThreadHistoryRequest(limit=5), manager)
    assert history == [{"checkpoint": {"checkpoint_id": "cp"}}]

