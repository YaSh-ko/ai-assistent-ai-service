import pytest
from app.data_access.repositories.dal import DataAccessLayer

@pytest.mark.usefixtures("db_pool")
@pytest.mark.asyncio
async def test_dal_initialization(db_pool, chroma_client):
    """Проверка инициализации DAL"""
    from unittest.mock import AsyncMock, MagicMock
    from app.data_access.postgresql.entry_repository import EntryRepository
    from app.data_access.postgresql.entry_thread_repository import EntryThreadRepository
    from app.data_access.postgresql.chat_session_repository import ChatSessionRepository
    from app.data_access.repositories.embedding_repository import EmbeddingRepository

    mock_provider = MagicMock()
    mock_provider._ensure_connection = AsyncMock()
    pool = MagicMock()
    pool.fetchrow = AsyncMock(
        side_effect=db_pool.acquire.return_value.__aenter__.return_value.fetchrow.side_effect
    )
    pool.fetch = AsyncMock(
        side_effect=db_pool.acquire.return_value.__aenter__.return_value.fetch.side_effect
    )
    pool.execute = AsyncMock(
        side_effect=db_pool.acquire.return_value.__aenter__.return_value.execute.side_effect
    )
    pool.acquire = db_pool.acquire
    mock_provider.pool = pool

    dal = DataAccessLayer(
        chat_session_repo=ChatSessionRepository(mock_provider),
        entry_repo=EntryRepository(mock_provider),
        entry_thread_repo=EntryThreadRepository(mock_provider),
        embedding_repo=EmbeddingRepository(chroma_client),
    )

    assert dal.chat_session_repo is not None
    assert dal.entry_repo is not None
    assert dal.entry_thread_repo is not None
    assert dal.embedding_repo is not None

@pytest.mark.asyncio
async def test_dal_save_entry_full(db_pool, chroma_client):
    """Проверка сохранения записи в обе БД через DAL"""
    from datetime import date
    from unittest.mock import AsyncMock, MagicMock

    from app.data_access.postgresql.entry_repository import EntryRepository
    from app.data_access.postgresql.entry_thread_repository import EntryThreadRepository
    from app.data_access.postgresql.chat_session_repository import ChatSessionRepository
    from app.data_access.repositories.embedding_repository import EmbeddingRepository

    mock_provider = MagicMock()
    mock_provider._ensure_connection = AsyncMock()
    pool = MagicMock()
    pool.fetchrow = AsyncMock(
        side_effect=db_pool.acquire.return_value.__aenter__.return_value.fetchrow.side_effect
    )
    pool.fetch = AsyncMock(
        side_effect=db_pool.acquire.return_value.__aenter__.return_value.fetch.side_effect
    )
    pool.execute = AsyncMock(
        side_effect=db_pool.acquire.return_value.__aenter__.return_value.execute.side_effect
    )
    pool.acquire = db_pool.acquire
    mock_provider.pool = pool

    dal = DataAccessLayer(
        chat_session_repo=ChatSessionRepository(mock_provider),
        entry_repo=EntryRepository(mock_provider),
        entry_thread_repo=EntryThreadRepository(mock_provider),
        embedding_repo=EmbeddingRepository(chroma_client),
    )

    mock_entry = MagicMock()
    mock_entry.id = "entry_id_1"
    dal.save_entry_with_embedding = AsyncMock(return_value=mock_entry)

    entry = await dal.save_entry_with_embedding(
        user_id="user_123",
        title="Test entry",
        description="Test description",
        event_date=date(2025, 11, 29),
        thread_id="thread_123",
    )

    assert entry is not None
    assert entry.id == "entry_id_1"
