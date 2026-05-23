"""
Tests for DatabaseFactory — 38 uncovered lines.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def reset_factory():
    """Reset singleton state between tests."""
    from app.factory.database_factory import DatabaseFactory
    DatabaseFactory._neo4j_instance = None
    DatabaseFactory._postgres_instance = None
    DatabaseFactory._chroma_instance = None
    DatabaseFactory._milvus_instance = None
    yield
    DatabaseFactory._neo4j_instance = None
    DatabaseFactory._postgres_instance = None
    DatabaseFactory._chroma_instance = None
    DatabaseFactory._milvus_instance = None


class TestCreateRelationalDatabase:
    def test_creates_postgres_provider(self):
        from app.factory.database_factory import DatabaseFactory

        mock_provider = MagicMock()
        with patch("app.factory.database_factory.PostgresProvider", return_value=mock_provider), \
             patch("app.core.config.settings") as s:
            s.DATABASE_CONFIG = {}
            result = DatabaseFactory.create_relational_database("postgres")

        assert result is mock_provider

    def test_singleton_returns_same_instance(self):
        from app.factory.database_factory import DatabaseFactory

        mock_provider = MagicMock()
        with patch("app.factory.database_factory.PostgresProvider", return_value=mock_provider), \
             patch("app.core.config.settings") as s:
            s.DATABASE_CONFIG = {}
            r1 = DatabaseFactory.create_relational_database()
            r2 = DatabaseFactory.create_relational_database()

        assert r1 is r2

    def test_unknown_provider_raises(self):
        from app.factory.database_factory import DatabaseFactory
        with pytest.raises(ValueError, match="Unknown relational database provider"):
            DatabaseFactory.create_relational_database("mysql")


class TestCreateGraphDatabase:
    @pytest.mark.asyncio
    async def test_creates_neo4j_provider(self):
        from app.factory.database_factory import DatabaseFactory

        mock_provider = AsyncMock()
        mock_provider.health_check = AsyncMock(return_value=True)

        with patch("app.factory.database_factory.Neo4jProvider", return_value=mock_provider), \
             patch("app.core.config.settings") as s:
            s.DATABASE_CONFIG = {}
            result = await DatabaseFactory.create_graph_database("neo4j")

        assert result is mock_provider

    @pytest.mark.asyncio
    async def test_health_check_failure_raises(self):
        from app.factory.database_factory import DatabaseFactory

        mock_provider = AsyncMock()
        mock_provider.health_check = AsyncMock(return_value=False)
        mock_provider.close = AsyncMock()

        with patch("app.factory.database_factory.Neo4jProvider", return_value=mock_provider), \
             patch("app.core.config.settings") as s:
            s.DATABASE_CONFIG = {}
            with pytest.raises(RuntimeError, match="Neo4j database is unavailable"):
                await DatabaseFactory.create_graph_database("neo4j")

    @pytest.mark.asyncio
    async def test_unknown_provider_raises(self):
        from app.factory.database_factory import DatabaseFactory
        with pytest.raises(ValueError, match="Unknown graph database provider"):
            await DatabaseFactory.create_graph_database("mongodb")

    @pytest.mark.asyncio
    async def test_singleton_returns_same_instance(self):
        from app.factory.database_factory import DatabaseFactory

        mock_provider = AsyncMock()
        mock_provider.health_check = AsyncMock(return_value=True)

        with patch("app.factory.database_factory.Neo4jProvider", return_value=mock_provider), \
             patch("app.core.config.settings") as s:
            s.DATABASE_CONFIG = {}
            r1 = await DatabaseFactory.create_graph_database()
            r2 = await DatabaseFactory.create_graph_database()

        assert r1 is r2


class TestCreateVectorStore:
    def test_creates_chroma_provider(self):
        from app.factory.database_factory import DatabaseFactory

        mock_provider = MagicMock()
        with patch("app.factory.database_factory.ChromaProvider", return_value=mock_provider), \
             patch("app.core.config.settings") as s:
            s.DATABASE_CONFIG = {}
            s.VECTOR_STORE_TYPE = "chroma"
            result = DatabaseFactory.create_vector_store("chroma")

        assert result is mock_provider

    def test_creates_milvus_provider(self):
        from app.factory.database_factory import DatabaseFactory

        mock_provider = MagicMock()
        with patch("app.factory.database_factory.MilvusProvider", return_value=mock_provider), \
             patch("app.core.config.settings") as s:
            s.DATABASE_CONFIG = {}
            s.VECTOR_STORE_TYPE = "milvus"
            result = DatabaseFactory.create_vector_store("milvus")

        assert result is mock_provider

    def test_unknown_provider_raises(self):
        from app.factory.database_factory import DatabaseFactory
        with patch("app.core.config.settings") as s:
            s.VECTOR_STORE_TYPE = "pinecone"
            with pytest.raises(ValueError, match="Unknown vector store provider"):
                DatabaseFactory.create_vector_store("pinecone")

    def test_chroma_singleton(self):
        from app.factory.database_factory import DatabaseFactory

        mock_provider = MagicMock()
        with patch("app.factory.database_factory.ChromaProvider", return_value=mock_provider), \
             patch("app.core.config.settings") as s:
            s.DATABASE_CONFIG = {}
            s.VECTOR_STORE_TYPE = "chroma"
            r1 = DatabaseFactory.create_vector_store("chroma")
            r2 = DatabaseFactory.create_vector_store("chroma")

        assert r1 is r2


class TestCloseAll:
    @pytest.mark.asyncio
    async def test_close_all_clears_instances(self):
        from app.factory.database_factory import DatabaseFactory

        mock_neo4j = AsyncMock()
        mock_neo4j.close = AsyncMock()
        mock_postgres = AsyncMock()
        mock_postgres.disconnect = AsyncMock()

        DatabaseFactory._neo4j_instance = mock_neo4j
        DatabaseFactory._postgres_instance = mock_postgres

        await DatabaseFactory.close_all()

        assert DatabaseFactory._neo4j_instance is None
        assert DatabaseFactory._postgres_instance is None
        mock_neo4j.close.assert_called_once()
        mock_postgres.disconnect.assert_called_once()
