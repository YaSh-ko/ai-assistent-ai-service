"""
Tests for BasePostgreSQLRepository.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.data_access.postgresql.base_repository import BasePostgreSQLRepository


@pytest.fixture
def mock_db_provider():
    """Mock database provider."""
    provider = AsyncMock()
    provider.pool = AsyncMock()
    provider._ensure_connection = AsyncMock()
    return provider


@pytest.fixture
def base_repo(mock_db_provider):
    """Create BasePostgreSQLRepository instance."""
    return BasePostgreSQLRepository(mock_db_provider)


class TestFetchOne:
    """Test fetch_one method."""
    
    @pytest.mark.asyncio
    async def test_fetch_one_success(self, base_repo, mock_db_provider):
        """Test successful fetch_one."""
        mock_record = {"id": 1, "name": "Test"}
        mock_db_provider.pool.fetchrow = AsyncMock(return_value=mock_record)
        
        # Mock the query lock as an async context manager
        mock_lock = AsyncMock()
        mock_lock.__aenter__ = AsyncMock(return_value=None)
        mock_lock.__aexit__ = AsyncMock(return_value=None)
        
        with patch('app.providers.databases.postgres_provider.PostgresProvider._query_lock', mock_lock):
            result = await base_repo.fetch_one("SELECT * FROM test WHERE id = $1", 1)
        
        assert result == mock_record
        mock_db_provider.pool.fetchrow.assert_called_once_with("SELECT * FROM test WHERE id = $1", 1)
    
    @pytest.mark.asyncio
    async def test_fetch_one_no_result(self, base_repo, mock_db_provider):
        """Test fetch_one with no result."""
        mock_db_provider.pool.fetchrow = AsyncMock(return_value=None)
        
        mock_lock = AsyncMock()
        mock_lock.__aenter__ = AsyncMock(return_value=None)
        mock_lock.__aexit__ = AsyncMock(return_value=None)
        
        with patch('app.providers.databases.postgres_provider.PostgresProvider._query_lock', mock_lock):
            result = await base_repo.fetch_one("SELECT * FROM test WHERE id = $1", 999)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_fetch_one_error(self, base_repo, mock_db_provider):
        """Test fetch_one with database error."""
        mock_db_provider.pool.fetchrow = AsyncMock(side_effect=Exception("DB error"))
        
        mock_lock = AsyncMock()
        mock_lock.__aenter__ = AsyncMock(return_value=None)
        mock_lock.__aexit__ = AsyncMock(return_value=None)
        
        with patch('app.providers.databases.postgres_provider.PostgresProvider._query_lock', mock_lock):
            with pytest.raises(Exception, match="DB error"):
                await base_repo.fetch_one("SELECT * FROM test", )


class TestFetchAll:
    """Test fetch_all method."""
    
    @pytest.mark.asyncio
    async def test_fetch_all_success(self, base_repo, mock_db_provider):
        """Test successful fetch_all."""
        mock_records = [
            {"id": 1, "name": "Test1"},
            {"id": 2, "name": "Test2"}
        ]
        mock_db_provider.pool.fetch = AsyncMock(return_value=mock_records)
        
        mock_lock = AsyncMock()
        mock_lock.__aenter__ = AsyncMock(return_value=None)
        mock_lock.__aexit__ = AsyncMock(return_value=None)
        
        with patch('app.providers.databases.postgres_provider.PostgresProvider._query_lock', mock_lock):
            result = await base_repo.fetch_all("SELECT * FROM test")
        
        assert result == mock_records
        mock_db_provider.pool.fetch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fetch_all_empty(self, base_repo, mock_db_provider):
        """Test fetch_all with no results."""
        mock_db_provider.pool.fetch = AsyncMock(return_value=[])
        
        mock_lock = AsyncMock()
        mock_lock.__aenter__ = AsyncMock(return_value=None)
        mock_lock.__aexit__ = AsyncMock(return_value=None)
        
        with patch('app.providers.databases.postgres_provider.PostgresProvider._query_lock', mock_lock):
            result = await base_repo.fetch_all("SELECT * FROM test WHERE id = $1", 999)
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_fetch_all_with_params(self, base_repo, mock_db_provider):
        """Test fetch_all with query parameters."""
        mock_records = [{"id": 1, "name": "Test"}]
        mock_db_provider.pool.fetch = AsyncMock(return_value=mock_records)
        
        mock_lock = AsyncMock()
        mock_lock.__aenter__ = AsyncMock(return_value=None)
        mock_lock.__aexit__ = AsyncMock(return_value=None)
        
        with patch('app.providers.databases.postgres_provider.PostgresProvider._query_lock', mock_lock):
            result = await base_repo.fetch_all("SELECT * FROM test WHERE id = $1", 1)
        
        assert len(result) == 1
        mock_db_provider.pool.fetch.assert_called_once_with("SELECT * FROM test WHERE id = $1", 1)
    
    @pytest.mark.asyncio
    async def test_fetch_all_error(self, base_repo, mock_db_provider):
        """Test fetch_all with database error."""
        mock_db_provider.pool.fetch = AsyncMock(side_effect=Exception("DB error"))
        
        mock_lock = AsyncMock()
        mock_lock.__aenter__ = AsyncMock(return_value=None)
        mock_lock.__aexit__ = AsyncMock(return_value=None)
        
        with patch('app.providers.databases.postgres_provider.PostgresProvider._query_lock', mock_lock):
            with pytest.raises(Exception, match="DB error"):
                await base_repo.fetch_all("SELECT * FROM test")


class TestExecute:
    """Test execute method."""
    
    @pytest.mark.asyncio
    async def test_execute_insert(self, base_repo, mock_db_provider):
        """Test execute with INSERT."""
        mock_db_provider.pool.execute = AsyncMock(return_value="INSERT 0 1")
        
        mock_lock = AsyncMock()
        mock_lock.__aenter__ = AsyncMock(return_value=None)
        mock_lock.__aexit__ = AsyncMock(return_value=None)
        
        with patch('app.providers.databases.postgres_provider.PostgresProvider._query_lock', mock_lock):
            result = await base_repo.execute("INSERT INTO test (name) VALUES ($1)", "Test")
        
        assert result == "INSERT 0 1"
        mock_db_provider.pool.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_update(self, base_repo, mock_db_provider):
        """Test execute with UPDATE."""
        mock_db_provider.pool.execute = AsyncMock(return_value="UPDATE 1")
        
        mock_lock = AsyncMock()
        mock_lock.__aenter__ = AsyncMock(return_value=None)
        mock_lock.__aexit__ = AsyncMock(return_value=None)
        
        with patch('app.providers.databases.postgres_provider.PostgresProvider._query_lock', mock_lock):
            result = await base_repo.execute("UPDATE test SET name = $1 WHERE id = $2", "New", 1)
        
        assert result == "UPDATE 1"
    
    @pytest.mark.asyncio
    async def test_execute_delete(self, base_repo, mock_db_provider):
        """Test execute with DELETE."""
        mock_db_provider.pool.execute = AsyncMock(return_value="DELETE 1")
        
        mock_lock = AsyncMock()
        mock_lock.__aenter__ = AsyncMock(return_value=None)
        mock_lock.__aexit__ = AsyncMock(return_value=None)
        
        with patch('app.providers.databases.postgres_provider.PostgresProvider._query_lock', mock_lock):
            result = await base_repo.execute("DELETE FROM test WHERE id = $1", 1)
        
        assert result == "DELETE 1"
    
    @pytest.mark.asyncio
    async def test_execute_error(self, base_repo, mock_db_provider):
        """Test execute with database error."""
        mock_db_provider.pool.execute = AsyncMock(side_effect=Exception("DB error"))
        
        mock_lock = AsyncMock()
        mock_lock.__aenter__ = AsyncMock(return_value=None)
        mock_lock.__aexit__ = AsyncMock(return_value=None)
        
        with patch('app.providers.databases.postgres_provider.PostgresProvider._query_lock', mock_lock):
            with pytest.raises(Exception, match="DB error"):
                await base_repo.execute("INSERT INTO test (name) VALUES ($1)", "Test")


class TestTransaction:
    """Test transaction context manager."""
    
    @pytest.mark.asyncio
    async def test_transaction_success(self, base_repo, mock_db_provider):
        """Test successful transaction."""
        mock_connection = AsyncMock()
        mock_transaction = MagicMock()
        
        # Make transaction methods async
        mock_transaction.start = AsyncMock()
        mock_transaction.commit = AsyncMock()
        mock_transaction.rollback = AsyncMock()
        
        mock_connection.transaction = MagicMock(return_value=mock_transaction)
        
        # Mock acquire context manager properly
        async def mock_acquire_cm(self):
            return mock_connection
        
        mock_acquire = MagicMock()
        mock_acquire.__aenter__ = mock_acquire_cm
        mock_acquire.__aexit__ = AsyncMock(return_value=None)
        mock_db_provider.pool.acquire = MagicMock(return_value=mock_acquire)
        
        async with base_repo.transaction() as conn:
            assert conn == mock_connection
        
        mock_transaction.start.assert_called_once()
        mock_transaction.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self, base_repo, mock_db_provider):
        """Test transaction rollback on error."""
        mock_connection = AsyncMock()
        mock_transaction = MagicMock()
        
        mock_transaction.start = AsyncMock()
        mock_transaction.rollback = AsyncMock()
        mock_transaction.commit = AsyncMock()
        
        mock_connection.transaction = MagicMock(return_value=mock_transaction)
        
        async def mock_acquire_cm(self):
            return mock_connection
        
        mock_acquire = MagicMock()
        mock_acquire.__aenter__ = mock_acquire_cm
        mock_acquire.__aexit__ = AsyncMock(return_value=None)
        mock_db_provider.pool.acquire = MagicMock(return_value=mock_acquire)
        
        with pytest.raises(ValueError):
            async with base_repo.transaction():
                raise ValueError("Test error")
        
        mock_transaction.start.assert_called_once()
        mock_transaction.rollback.assert_called_once()


class TestHandleError:
    """Test error handling."""
    
    @pytest.mark.asyncio
    async def test_handle_error_raises(self, base_repo):
        """Test that handle_error re-raises the exception."""
        test_error = Exception("Test error")
        
        with pytest.raises(Exception) as exc_info:
            await base_repo.handle_error(test_error)
        
        assert str(exc_info.value) == "Test error"


class TestEnsureConnection:
    """Test connection ensuring."""
    
    @pytest.mark.asyncio
    async def test_ensure_connection_called(self, base_repo, mock_db_provider):
        """Test that _ensure_connection is called before queries."""
        mock_db_provider.pool.fetchrow = AsyncMock(return_value=None)
        
        mock_lock = AsyncMock()
        mock_lock.__aenter__ = AsyncMock(return_value=None)
        mock_lock.__aexit__ = AsyncMock(return_value=None)
        
        with patch('app.providers.databases.postgres_provider.PostgresProvider._query_lock', mock_lock):
            await base_repo.fetch_one("SELECT 1")
        
        mock_db_provider._ensure_connection.assert_called()
