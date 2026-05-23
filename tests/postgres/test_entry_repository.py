import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from app.data_access.postgresql.entry_repository import EntryRepository


@pytest.fixture
def mock_provider(db_pool):
    """Create a mock db_provider wrapping the db_pool fixture."""
    provider = MagicMock()
    provider._ensure_connection = AsyncMock()
    pool = MagicMock()
    pool.fetchrow = AsyncMock(side_effect=db_pool.acquire.return_value.__aenter__.return_value.fetchrow.side_effect)
    pool.fetch = AsyncMock(side_effect=db_pool.acquire.return_value.__aenter__.return_value.fetch.side_effect)
    pool.execute = AsyncMock(side_effect=db_pool.acquire.return_value.__aenter__.return_value.execute.side_effect)
    pool.acquire = db_pool.acquire
    provider.pool = pool
    return provider


@pytest.mark.asyncio
async def test_entry_crud(mock_provider):
    """Полный цикл CRUD для entries"""
    repo = EntryRepository(mock_provider)

    mock_lock = AsyncMock()
    mock_lock.__aenter__ = AsyncMock(return_value=None)
    mock_lock.__aexit__ = AsyncMock(return_value=None)

    with patch('app.providers.databases.postgres_provider.PostgresProvider._query_lock', mock_lock):
        # CREATE
        entry = await repo.create(
            user_id="user_123",
            title="Встреча с инвестором",
            description="Обсудили финансирование $100k",
            event_date=date(2025, 11, 25)
        )

        assert entry is not None
        assert entry['title'] == "Встреча с инвестором"
        entry_id = entry['id']

        # READ
        retrieved = await repo.get_by_id(entry_id)
        assert retrieved is not None

        # UPDATE
        await repo.update(
            entry_id,
            description="Обсудили финансирование $200k"
        )

        # DELETE
        await repo.delete(entry_id)
        deleted = await repo.get_by_id(entry_id)
        assert deleted is None
