import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.data_access.postgresql.base_repository import BasePostgreSQLRepository


@pytest.fixture
def mock_provider(db_pool):
    """Create a mock db_provider wrapping the db_pool fixture."""
    provider = MagicMock()
    provider._ensure_connection = AsyncMock()
    # db_pool is a MagicMock pool; we need pool.fetchrow/fetch/execute to be AsyncMocks
    # The conftest sets up connection.fetchrow but BasePostgreSQLRepository calls pool.fetchrow directly
    pool = MagicMock()
    pool.fetchrow = AsyncMock(side_effect=db_pool.acquire.return_value.__aenter__.return_value.fetchrow.side_effect)
    pool.fetch = AsyncMock(side_effect=db_pool.acquire.return_value.__aenter__.return_value.fetch.side_effect)
    pool.execute = AsyncMock(side_effect=db_pool.acquire.return_value.__aenter__.return_value.execute.side_effect)
    pool.acquire = db_pool.acquire
    provider.pool = pool
    return provider


@pytest.mark.asyncio
async def test_base_repository_fetch_one(mock_provider):
    """Проверка получения одной записи"""
    repo = BasePostgreSQLRepository(mock_provider)

    mock_lock = AsyncMock()
    mock_lock.__aenter__ = AsyncMock(return_value=None)
    mock_lock.__aexit__ = AsyncMock(return_value=None)

    with patch('app.providers.databases.postgres_provider.PostgresProvider._query_lock', mock_lock):
        await repo.execute(
            "INSERT INTO test_table (id, name) VALUES ($1, $2)",
            1, "Test"
        )

        result = await repo.fetch_one(
            "SELECT * FROM test_table WHERE id = $1",
            1
        )

    assert result is not None
    assert result['name'] == "Test"


@pytest.mark.asyncio
async def test_base_repository_transaction(mock_provider):
    """Проверка транзакций"""
    repo = BasePostgreSQLRepository(mock_provider)

    async with repo.transaction() as conn:
        await conn.execute("INSERT INTO test_table (id, name) VALUES ($1, $2)", 2, "Test2")
        await conn.execute("UPDATE test_table SET name = $1 WHERE id = $2", "Updated", 2)

    mock_lock = AsyncMock()
    mock_lock.__aenter__ = AsyncMock(return_value=None)
    mock_lock.__aexit__ = AsyncMock(return_value=None)

    with patch('app.providers.databases.postgres_provider.PostgresProvider._query_lock', mock_lock):
        result = await repo.fetch_one("SELECT * FROM test_table WHERE id = $1", 2)

    assert result is not None
