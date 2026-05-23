from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.chat_session import ChatSession
from app.services.session_manager import SessionManager


def _session(thread_id: str = "t-1", states=None, history=None) -> ChatSession:
    return ChatSession(
        thread_id=thread_id,
        user_id="u-1",
        title=None,
        status="active",
        created_at=datetime.now(),
        last_active_at=datetime.now(),
        history=history or [],
        context={},
        metadata={},
        states=states or [],
    )


@pytest.mark.asyncio
async def test_save_thread_state_and_parent_checkpoint():
    repo = AsyncMock()
    manager = SessionManager(repo)
    manager.get_session = AsyncMock(return_value=_session(states=[{"checkpoint": {"checkpoint_id": "old", "thread_id": "t-1", "checkpoint_ns": ""}}]))
    manager.update_session = AsyncMock(return_value=True)

    cp_id = await manager.save_thread_state(
        thread_id="t-1",
        run_id="r-1",
        assistant_id="a-1",
        final_messages=[{"type": "human", "content": "hi"}],
    )

    assert cp_id is not None
    payload = manager.update_session.call_args.args[1]
    assert payload["states"][0]["parent_checkpoint"]["checkpoint_id"] == "old"
    assert payload["history"] == [{"type": "human", "content": "hi"}]


@pytest.mark.asyncio
async def test_get_messages_by_checkpoint_and_fallback():
    repo = AsyncMock()
    manager = SessionManager(repo)
    session = _session(
        states=[{"checkpoint": {"checkpoint_id": "cp-1"}, "values": {"messages": [{"type": "ai", "content": "x"}]}}],
        history=[{"type": "human", "content": "fallback"}],
    )
    manager.get_session = AsyncMock(return_value=session)

    assert await manager.get_messages_by_checkpoint("t-1", "cp-1") == [{"type": "ai", "content": "x"}]
    assert await manager.get_messages_by_checkpoint("t-1", "missing") == [{"type": "human", "content": "fallback"}]

