import asyncio
import logging
from typing import Optional
from threading import Lock
from app.core.interfaces.i_graph_database import IGraphDatabase
from app.interfaces.relational_database import IRelationalDatabase
from app.interfaces.vector_store import IVectorStore
from app.providers.databases.postgres_provider import PostgresProvider
from app.providers.databases.neo4j_provider import Neo4jProvider
from app.providers.databases.chroma_provider import ChromaProvider
from app.data_access.neo4j.graph_repository import GraphRepository

logger = logging.getLogger(__name__)


class DatabaseFactory:
    """
    Factory for creating database instances with singleton pattern support.
    """
    _neo4j_instance: Optional[Neo4jProvider] = None
    _neo4j_lock = Lock()
    
    _postgres_instance: Optional[PostgresProvider] = None
    _postgres_lock = Lock()
    
    _chroma_instance: Optional[ChromaProvider] = None
    _chroma_lock = Lock()

    @staticmethod
    def create_relational_database(provider_type: str = "postgres") -> IRelationalDatabase:
        """Create a relational database instance with singleton pattern."""
        from app.core.config import settings
        
        if provider_type != "postgres":
            raise ValueError(f"Unknown relational database provider: {provider_type}")
            
        if DatabaseFactory._postgres_instance is not None:
            return DatabaseFactory._postgres_instance
            
        with DatabaseFactory._postgres_lock:
            if DatabaseFactory._postgres_instance is not None:
                return DatabaseFactory._postgres_instance
                
            # Pass configuration
            provider = PostgresProvider(config=settings.DATABASE_CONFIG)
            DatabaseFactory._postgres_instance = provider
            return provider

    @staticmethod
    async def create_graph_database(provider_type: str = "neo4j", force_new: bool = False) -> IGraphDatabase:
        """
        Create a graph database instance with singleton pattern.
        """
        from app.core.config import settings
        
        if provider_type != "neo4j":
            raise ValueError(f"Unknown graph database provider: {provider_type}")

        # Use singleton pattern unless force_new is True
        if not force_new and DatabaseFactory._neo4j_instance is not None:
            logger.info("Returning existing Neo4j provider instance (singleton)")
            return DatabaseFactory._neo4j_instance

        with DatabaseFactory._neo4j_lock:
            # Double-check locking pattern
            if not force_new and DatabaseFactory._neo4j_instance is not None:
                return DatabaseFactory._neo4j_instance

            logger.info("Creating new Neo4j provider instance...")
            # Pass configuration
            provider = Neo4jProvider(config=settings.DATABASE_CONFIG)
            
            # Perform health check (fail-fast)
            logger.info("Performing health check on Neo4j provider...")
            health_ok = await provider.health_check()
            
            if not health_ok:
                logger.error("Neo4j health check failed! Database is unavailable.")
                await provider.close()
                raise RuntimeError(
                    "Neo4j database is unavailable. Please check your Neo4j connection settings and ensure the database is running."
                )
            
            logger.info("Neo4j health check passed successfully.")
            
            # Cache the instance (singleton)
            if not force_new:
                DatabaseFactory._neo4j_instance = provider
                logger.info("Neo4j provider instance cached for reuse.")
            
            return provider

    @staticmethod
    async def create_graph_repository(force_new: bool = False) -> GraphRepository:
        """
        Create a GraphRepository instance with Neo4j provider.
        """
        logger.info("Creating GraphRepository instance...")
        db = await DatabaseFactory.create_graph_database(force_new=force_new)
        graph_repo = GraphRepository(db)
        logger.info("GraphRepository instance created successfully.")
        return graph_repo

    @staticmethod
    def create_vector_store(provider_type: str = None) -> IVectorStore:
        """Create a Chroma vector store instance with singleton pattern."""
        from app.core.config import settings

        if provider_type is None:
            provider_type = settings.VECTOR_STORE_TYPE

        if provider_type != "chroma":
            raise ValueError(f"Unknown vector store provider: {provider_type}. Use 'chroma'")

        if DatabaseFactory._chroma_instance is not None:
            return DatabaseFactory._chroma_instance

        with DatabaseFactory._chroma_lock:
            if DatabaseFactory._chroma_instance is not None:
                return DatabaseFactory._chroma_instance

            provider = ChromaProvider(config=settings.DATABASE_CONFIG)
            DatabaseFactory._chroma_instance = provider
            return provider

    @staticmethod
    async def close_graph_database():
        """Close the singleton Neo4j provider if it exists."""
        if DatabaseFactory._neo4j_instance is not None:
            logger.info("Closing Neo4j provider instance...")
            await DatabaseFactory._neo4j_instance.close()
            DatabaseFactory._neo4j_instance = None
            logger.info("Neo4j provider instance closed.")
            
    @staticmethod
    async def close_relational_database():
        """Close the singleton Postgres provider if it exists."""
        if DatabaseFactory._postgres_instance is not None:
            logger.info("Closing Postgres provider instance...")
            await DatabaseFactory._postgres_instance.disconnect()
            DatabaseFactory._postgres_instance = None
            logger.info("Postgres provider instance closed.")

    @staticmethod
    async def close_all():
        """Close all singleton database providers."""
        logger.info("Closing all database connections...")
        await DatabaseFactory.close_graph_database()
        await DatabaseFactory.close_relational_database()
        logger.info("All database connections closed.")

    @staticmethod
    async def create_dal_async() -> 'DataAccessLayer':
        """
        Async factory for DataAccessLayer.
        """
        from app.core.config import settings
        from app.data_access.repositories.dal import DataAccessLayer
        from app.data_access.repositories.embedding_repository import EmbeddingRepository
        
        chroma_client = DatabaseFactory.create_vector_store()  # Uses configured type
        embedding_repo = EmbeddingRepository(chroma_client)
        
        if settings.DATABASE_TYPE == "postgres":
            from app.data_access.postgresql.entry_repository import EntryRepository
            from app.data_access.postgresql.entry_thread_repository import EntryThreadRepository
            from app.data_access.postgresql.chat_session_repository import ChatSessionRepository

            provider = DatabaseFactory.create_relational_database()
            if not provider.pool:
                await provider.connect()

            return DataAccessLayer(
                chat_session_repo=ChatSessionRepository(provider),
                entry_repo=EntryRepository(provider),
                entry_thread_repo=EntryThreadRepository(provider),
                embedding_repo=embedding_repo,
            )
        else:
            raise ValueError(f"Unsupported DATABASE_TYPE: {settings.DATABASE_TYPE}")
