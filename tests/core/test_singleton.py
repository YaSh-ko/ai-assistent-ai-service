import pytest
from app.factory.database_factory import DatabaseFactory
from app.providers.databases.postgres_provider import PostgresProvider
from app.providers.databases.chroma_provider import ChromaProvider

@pytest.mark.asyncio
async def test_postgres_singleton():
    """Verify that create_relational_database returns the same instance."""
    # Reset singleton for test
    DatabaseFactory._postgres_instance = None
    
    db1 = DatabaseFactory.create_relational_database("postgres")
    db2 = DatabaseFactory.create_relational_database("postgres")
    
    assert db1 is db2
    assert isinstance(db1, PostgresProvider)
    
    # Clean up
    await DatabaseFactory.close_relational_database()
    assert DatabaseFactory._postgres_instance is None

def test_chroma_singleton():
    """Verify that create_vector_store returns the same instance."""
    # Reset singleton for test
    DatabaseFactory._chroma_instance = None
    
    db1 = DatabaseFactory.create_vector_store("chroma")
    db2 = DatabaseFactory.create_vector_store("chroma")
    
    assert db1 is db2
    assert isinstance(db1, ChromaProvider)
    
    # Clean up (manually since no close method for chroma singleton exposed yet)
    DatabaseFactory._chroma_instance = None

@pytest.mark.asyncio
async def test_neo4j_singleton():
    """Verify that create_graph_database returns the same instance."""
    # Reset singleton for test
    if DatabaseFactory._neo4j_instance:
        await DatabaseFactory.close_graph_database()
    
    # We need to mock Neo4j connection or it will fail health check
    from unittest.mock import patch, AsyncMock
    
    with patch("app.providers.databases.neo4j_provider.Neo4jProvider.health_check", new_callable=AsyncMock) as mock_health:
        mock_health.return_value = True
        
        db1 = await DatabaseFactory.create_graph_database("neo4j")
        db2 = await DatabaseFactory.create_graph_database("neo4j")
        
        assert db1 is db2
        
        # Test force_new
        db3 = await DatabaseFactory.create_graph_database("neo4j", force_new=True)
        assert db3 is not db1
        
        await DatabaseFactory.close_graph_database()
