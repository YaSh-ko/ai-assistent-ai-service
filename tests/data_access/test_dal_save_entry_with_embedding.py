from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.data_access.repositories.dal import DataAccessLayer


def _make_dal(entry_repo, embedding_repo, entry_thread_repo):
    return DataAccessLayer(
        session_repo=MagicMock(),
        chat_session_repo=MagicMock(),
        entry_repo=entry_repo,
        entry_thread_repo=entry_thread_repo,
        goal_thread_repo=MagicMock(),
        experiment_thread_repo=MagicMock(),
        analysis_thread_repo=MagicMock(),
        embedding_repo=embedding_repo,
    )


@pytest.mark.asyncio
async def test_save_entry_with_embedding_creates_entry_embedding_and_link():
    entry_repo = MagicMock()
    entry_repo.create = AsyncMock(return_value={"id": "entry-1", "title": "T"})
    embedding_repo = MagicMock()
    embedding_repo.add_embedding = AsyncMock()
    entry_thread_repo = MagicMock()
    entry_thread_repo.create = AsyncMock()

    dal = _make_dal(entry_repo, embedding_repo, entry_thread_repo)
    result = await dal.save_entry_with_embedding(
        user_id="u-1",
        title="Title",
        description="Description",
        event_date=date(2026, 1, 1),
        thread_id="thread-1",
        embedding=[0.5, 0.2],
    )

    assert isinstance(result, SimpleNamespace)
    assert result.id == "entry-1"
    embedding_repo.add_embedding.assert_awaited_once()
    entry_thread_repo.create.assert_awaited_once_with("entry-1", "thread-1", "BELONGS_TO", "u-1")


@pytest.mark.asyncio
async def test_save_entry_with_embedding_uses_default_embedding_and_raises_on_empty_entry():
    entry_repo = MagicMock()
    entry_repo.create = AsyncMock(return_value={"id": "entry-2"})
    embedding_repo = MagicMock()
    embedding_repo.add_embedding = AsyncMock()
    entry_thread_repo = MagicMock()
    entry_thread_repo.create = AsyncMock()
    dal = _make_dal(entry_repo, embedding_repo, entry_thread_repo)

    await dal.save_entry_with_embedding(
        user_id="u-1",
        title="Title",
        description="Description",
        event_date=date(2026, 1, 1),
    )
    embedding_arg = embedding_repo.add_embedding.call_args.kwargs["embedding"]
    assert len(embedding_arg) == 1024
    assert set(embedding_arg) == {0.0}

    entry_repo.create = AsyncMock(return_value=None)
    with pytest.raises(RuntimeError, match="Failed to create entry in PostgreSQL"):
        await dal.save_entry_with_embedding(
            user_id="u-1",
            title="Title",
            description="Description",
            event_date=date(2026, 1, 1),
        )

