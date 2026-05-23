import pytest
import sys
import os
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.providers.databases.neo4j_provider import Neo4jProvider


class TestNeo4jProvider:
    """Unit tests for Neo4jProvider using mocked Neo4j driver."""

@pytest.fixture
def mock_driver():
    """Create a mocked Neo4j driver."""
    driver = Mock()
    driver.close = AsyncMock()
    driver.session = Mock()  # Add this line
    return driver

@pytest.fixture
def mock_session():
    """Create a mocked Neo4j session."""
    session = AsyncMock()  # Use AsyncMock instead of MagicMock
    session.run = AsyncMock()
    session.execute_read = AsyncMock()
    session.execute_write = AsyncMock()
    session.close = AsyncMock()
    return session

import pytest_asyncio

@pytest_asyncio.fixture
async def provider_with_mock(mock_driver, mock_session):
    """Create Neo4jProvider with mocked driver."""
    # Configure the session to work properly with async context manager
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    
    # Link session to driver
    mock_driver.session.return_value = mock_session
    
    with patch('app.providers.databases.neo4j_provider.AsyncGraphDatabase.driver') as mock_driver_factory:
        mock_driver_factory.return_value = mock_driver
        # Patch settings in the provider module
        with patch('app.providers.databases.neo4j_provider.settings') as mock_settings:
            mock_settings.NEO4J_URI = "bolt://test:7687"
            mock_settings.NEO4J_USERNAME = "test_user"
            mock_settings.NEO4J_PASSWORD = "test_password"
            
            provider = Neo4jProvider()
            # Don't manually set provider.driver - let the provider initialize it
            yield provider

@pytest.mark.asyncio
async def test_execute_read_success(provider_with_mock, mock_driver, mock_session):
    """Test successful read query execution."""
    # Setup mock result
    mock_result = [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25}
    ]
    
    # Create a proper mock cursor
    mock_cursor = AsyncMock()
    mock_cursor.data = AsyncMock(return_value=mock_result)
    
    # Configure session methods
    mock_session.run.return_value = mock_cursor
    mock_session.execute_read.return_value = mock_result
    
    # Execute
    result = await provider_with_mock.execute_read(
        "MATCH (n:Person) RETURN n.name as name, n.age as age",
        {}
    )
    
    # Verify
    assert len(result) == 2
    assert result[0]["name"] == "Alice"
    assert result[1]["age"] == 25
    mock_session.execute_read.assert_called_once()

@pytest.mark.asyncio
async def test_execute_write_success(provider_with_mock, mock_driver, mock_session):
    """Test successful write query execution."""
    # Setup mock result
    mock_summary_data = {
        "nodes_created": 1,
        "properties_set": 2,
        "nodes_deleted": 0,
        "relationships_created": 0,
        "relationships_deleted": 0
    }
    
    # Configure session to return the summary data directly
    mock_session.execute_write.return_value = mock_summary_data
    
    # Execute
    result = await provider_with_mock.execute_write(
        "CREATE (n:Person {name: $name, age: $age}) RETURN n",
        {"name": "Charlie", "age": 35}
    )
    
    # Verify
    assert result["nodes_created"] == 1
    assert result["properties_set"] == 2
    assert result["nodes_deleted"] == 0
    mock_session.execute_write.assert_called_once()

@pytest.mark.asyncio
async def test_health_check_success(provider_with_mock, mock_driver, mock_session):
    """Test successful health check."""
    # Setup
    mock_session.execute_read.return_value = [{"ping": 1}]
    
    # Execute
    result = await provider_with_mock.health_check()
    
    # Verify
    assert result is True
    mock_session.execute_read.assert_called_once()

@pytest.mark.asyncio
async def test_health_check_failure(provider_with_mock, mock_driver, mock_session):
    """Test health check failure."""
    # Setup
    mock_session.execute_read.side_effect = Exception("Connection failed")
    
    # Execute
    result = await provider_with_mock.health_check()
    
    # Verify
    assert result is False
    mock_session.execute_read.assert_called_once()

@pytest.mark.asyncio
async def test_close(provider_with_mock, mock_driver):
    """Test closing the driver."""
    # Execute
    await provider_with_mock.close()
    
    # Verify
    mock_driver.close.assert_called_once()

@pytest.mark.asyncio
async def test_execute_read_error_handling(provider_with_mock, mock_driver, mock_session):
    """Test error handling in execute_read."""
    # Setup
    mock_session.execute_read.side_effect = Exception("Query execution failed")
    
    # Execute and verify exception is raised
    with pytest.raises(Exception, match="Query execution failed"):
        await provider_with_mock.execute_read("INVALID QUERY", {})

@pytest.mark.asyncio
async def test_execute_write_error_handling(provider_with_mock, mock_driver, mock_session):
    """Test error handling in execute_write."""
    # Setup
    mock_session.execute_write.side_effect = Exception("Write operation failed")
    
    # Execute and verify exception is raised
    with pytest.raises(Exception, match="Write operation failed"):
        await provider_with_mock.execute_write("INVALID WRITE", {})