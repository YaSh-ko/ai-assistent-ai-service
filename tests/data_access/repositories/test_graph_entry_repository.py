from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.data_access.repositories.entry_repository import EntryRepository


@pytest.mark.asyncio
async def test_create_entry_formats_timestamp_and_returns_id():
    repo = EntryRepository(MagicMock())
    repo._execute_write = AsyncMock(return_value={"id": "e-1"})

    result = await repo.create_entry(
        entry_id="e-1",
        user_id="u-1",
        session_id="s-1",
        timestamp=datetime(2026, 1, 1),
        content="text",
        word_count=10,
    )

    assert result == "e-1"
    call_params = repo._execute_write.call_args.args[1]
    assert call_params["entry_id"] == "e-1"
    assert call_params["timestamp"] == "2026-01-01T00:00:00"


@pytest.mark.asyncio
async def test_get_entry_returns_none_when_not_found():
    repo = EntryRepository(MagicMock())
    repo._execute_read = AsyncMock(return_value=[])

    result = await repo.get_entry("missing")

    assert result is None


@pytest.mark.asyncio
async def test_update_entry_branches():
    repo = EntryRepository(MagicMock())
    repo._execute_write = AsyncMock(return_value={"properties_set": 1})

    assert await repo.update_entry("e-1", {}) is False
    assert await repo.update_entry("e-1", {"content": "new"}) is True


@pytest.mark.asyncio
async def test_delete_and_find_by_user():
    repo = EntryRepository(MagicMock())
    repo._execute_write = AsyncMock(return_value={"nodes_deleted": 1})
    repo._execute_read = AsyncMock(return_value=[{"e": {"id": "e-1"}}])

    assert await repo.delete_entry("e-1") is True
    assert await repo.find_by_user("u-1", limit=5) == [{"id": "e-1"}]

