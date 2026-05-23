import pytest
import sys
import os
import asyncio
from unittest.mock import Mock, AsyncMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.data_access.neo4j.graph_repository import GraphRepository

@pytest.fixture
def mock_neo4j_provider():
    """Create a mocked Neo4j provider."""
    provider = AsyncMock()
    provider.execute_read = AsyncMock()
    provider.execute_write = AsyncMock()
    provider.health_check = AsyncMock(return_value=True)
    provider.close = AsyncMock()
    return provider


@pytest.fixture
def graph_repository(mock_neo4j_provider):
    """Create GraphRepository with mocked provider."""
    return GraphRepository(mock_neo4j_provider)


@pytest.mark.asyncio
async def test_create_node_success(graph_repository, mock_neo4j_provider):
    """Test successful node creation."""
    # Setup
    mock_result = {
        "nodes_created": 1,
        "properties_set": 2
    }
    mock_neo4j_provider.execute_write.return_value = mock_result
    
    # Execute
    result = await graph_repository.create_node(
        label="Person",
        properties={"name": "John", "age": 30}
    )
    
    # Verify
    assert result == mock_result
    mock_neo4j_provider.execute_write.assert_called_once()


@pytest.mark.asyncio
async def test_find_nodes_by_label(graph_repository, mock_neo4j_provider):
    """Test finding nodes by label."""
    # Setup
    mock_nodes = [
        {"name": "John", "age": 30},
        {"name": "Jane", "age": 25}
    ]
    mock_neo4j_provider.execute_read.return_value = mock_nodes
    
    # Execute
    result = await graph_repository.find_nodes_by_label("Person")
    
    # Verify
    assert result == mock_nodes
    mock_neo4j_provider.execute_read.assert_called_once()


@pytest.mark.asyncio
async def test_create_relationship(graph_repository, mock_neo4j_provider):
    """Test creating relationship between nodes."""
    # Setup
    mock_result = {
        "relationships_created": 1,
        "properties_set": 1
    }
    mock_neo4j_provider.execute_write.return_value = mock_result
    
    # Execute
    result = await graph_repository.create_relationship(
        from_id=1,
        to_id=2,
        rel_type="KNOWS",
        properties={"since": 2020}
    )
    
    # Verify
    assert result == mock_result
    mock_neo4j_provider.execute_write.assert_called_once()


@pytest.mark.asyncio
async def test_find_relationships(graph_repository, mock_neo4j_provider):
    """Test finding relationships."""
    # Setup
    mock_relationships = [
        {"from": "John", "to": "Jane", "type": "KNOWS"}
    ]
    mock_neo4j_provider.execute_read.return_value = mock_relationships
    
    # Execute
    result = await graph_repository.find_relationships(
        from_label="Person",
        to_label="Person",
        rel_type="KNOWS"
    )
    
    # Verify
    assert result == mock_relationships
    mock_neo4j_provider.execute_read.assert_called_once()


@pytest.mark.asyncio
async def test_delete_node(graph_repository, mock_neo4j_provider):
    """Test deleting a node."""
    # Setup
    mock_result = {
        "nodes_deleted": 1
    }
    mock_neo4j_provider.execute_write.return_value = mock_result
    
    # Execute
    result = await graph_repository.delete_node(node_id=123)
    
    # Verify
    assert result == mock_result
    mock_neo4j_provider.execute_write.assert_called_once()


@pytest.mark.asyncio
async def test_update_node_properties(graph_repository, mock_neo4j_provider):
    """Test updating node properties."""
    # Setup
    mock_result = {
        "properties_set": 2
    }
    mock_neo4j_provider.execute_write.return_value = mock_result
    
    # Execute
    result = await graph_repository.update_node_properties(
        node_id=123,
        properties={"name": "John Updated", "age": 31}
    )
    
    # Verify
    assert result == mock_result
    mock_neo4j_provider.execute_write.assert_called_once()


@pytest.mark.asyncio
async def test_execute_custom_query(graph_repository, mock_neo4j_provider):
    """Test executing custom query."""
    # Setup
    mock_result = [{"count": 5}]
    mock_neo4j_provider.execute_read.return_value = mock_result
    
    # Execute
    result = await graph_repository.execute_custom_query(
        "MATCH (n) RETURN count(n) as count"
    )
    
    # Verify
    assert result == mock_result
    mock_neo4j_provider.execute_read.assert_called_once()


@pytest.mark.asyncio
async def test_health_check(graph_repository, mock_neo4j_provider):
    """Test health check."""
    # Setup
    mock_neo4j_provider.health_check.return_value = True
    
    # Execute
    result = await graph_repository.health_check()
    
    # Verify
    assert result is True
    mock_neo4j_provider.health_check.assert_called_once()