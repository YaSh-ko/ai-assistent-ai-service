import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.providers.databases.postgres_provider import PostgresProvider

@pytest.fixture
def mock_pool():
    pool = MagicMock()
    connection = AsyncMock()
    
    # Setup connection context manager
    cm = AsyncMock()
    pool.acquire.return_value = cm
    cm.__aenter__.return_value = connection
    cm.__aexit__.return_value = None
    
    # Setup transaction context manager
    tx_cm = AsyncMock()
    connection.transaction = MagicMock(return_value=tx_cm)
    tx_cm.__aenter__.return_value = connection
    tx_cm.__aexit__.return_value = None
    
    # Setup direct pool methods (PostgresProvider calls pool.fetch/fetchrow/execute directly)
    pool.fetch = AsyncMock(return_value=[{"id": 1, "name": "Test"}])
    pool.fetchrow = AsyncMock(return_value={"id": 1, "name": "Test"})
    pool.execute = AsyncMock(return_value="INSERT 0 1")
    pool.close = AsyncMock()
    
    return pool

@pytest.mark.asyncio
async def test_connect(mock_pool):
    """Test connection initialization."""
    with patch("app.providers.databases.postgres_provider.asyncpg.create_pool", new=AsyncMock(return_value=mock_pool)) as mock_create_pool:
        provider = PostgresProvider()
        await provider.connect()
        
        assert provider.pool == mock_pool
        mock_create_pool.assert_called_once()

@pytest.mark.asyncio
async def test_disconnect(mock_pool):
    """Test connection closing."""
    provider = PostgresProvider()
    provider.pool = mock_pool
    
    await provider.disconnect()
    
    assert provider.pool is None
    mock_pool.close.assert_called_once()

@pytest.mark.asyncio
async def test_execute(mock_pool):
    """Test execute method."""
    provider = PostgresProvider()
    provider.pool = mock_pool
    provider._loop = asyncio.get_event_loop()
    
    await provider.execute("INSERT INTO test VALUES ($1)", {"val": 1})
    
    # Verify execute called on pool
    mock_pool.execute.assert_called_once()

@pytest.mark.asyncio
async def test_fetch_all(mock_pool):
    """Test fetch_all method."""
    provider = PostgresProvider()
    provider.pool = mock_pool
    provider._loop = asyncio.get_event_loop()
    
    result = await provider.fetch_all("SELECT * FROM test")
    
    assert len(result) == 1
    assert result[0]["name"] == "Test"
    
    mock_pool.fetch.assert_called_once()

@pytest.mark.asyncio
async def test_fetch_one(mock_pool):
    """Test fetch_one method."""
    provider = PostgresProvider()
    provider.pool = mock_pool
    provider._loop = asyncio.get_event_loop()
    
    result = await provider.fetch_one("SELECT * FROM test WHERE id=$1", {"id": 1})
    
    assert result["name"] == "Test"
    
    mock_pool.fetchrow.assert_called_once()

@pytest.mark.asyncio
async def test_transaction(mock_pool):
    """Test transaction context manager."""
    provider = PostgresProvider()
    provider.pool = mock_pool
    
    async with provider.transaction() as conn:
        await conn.execute("TEST")
        
    connection = mock_pool.acquire.return_value.__aenter__.return_value
    connection.transaction.assert_called_once()
