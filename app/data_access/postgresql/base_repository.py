from typing import Any, List, Optional, Dict
import asyncpg
from contextlib import asynccontextmanager
import logging
from app.interfaces.relational_database import IRelationalDatabase
from app.data_access.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class DatabaseError(RuntimeError):
    """Raised when a PostgreSQL repository operation fails."""

class BasePostgreSQLRepository(BaseRepository):
    """
    Base repository for PostgreSQL operations.
    """
    def __init__(self, db_provider: IRelationalDatabase):
        self.db_provider = db_provider

    async def fetch_one(self, query: str, *args: Any) -> Optional[Dict[str, Any]]:
        """Fetch a single row."""
        from app.providers.databases.postgres_provider import PostgresProvider
        await self.db_provider._ensure_connection()
        async with PostgresProvider._query_lock:
            try:
                record = await self.db_provider.pool.fetchrow(query, *args)
                return dict(record) if record else None
            except Exception as e:
                logger.error(f"Error executing fetch_one: {query}")
                await self.handle_error(e)
                return None

    async def fetch_all(self, query: str, *args: Any) -> List[Dict[str, Any]]:
        """Fetch all rows."""
        from app.providers.databases.postgres_provider import PostgresProvider
        await self.db_provider._ensure_connection()
        async with PostgresProvider._query_lock:
            try:
                records = await self.db_provider.pool.fetch(query, *args)
                return [dict(record) for record in records]
            except Exception as e:
                logger.error(f"Error executing fetch_all: {query}")
                await self.handle_error(e)
                return []

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query (INSERT, UPDATE, DELETE)."""
        from app.providers.databases.postgres_provider import PostgresProvider
        await self.db_provider._ensure_connection()
        async with PostgresProvider._query_lock:
            try:
                return await self.db_provider.pool.execute(query, *args)
            except Exception as e:
                logger.error(f"Error executing command: {query}")
                await self.handle_error(e)
                return ""

    @asynccontextmanager
    async def transaction(self):
        """Context manager for transactions."""
        await self.db_provider._ensure_connection()
        async with self.db_provider.pool.acquire() as connection:
            transaction = connection.transaction()
            try:
                await transaction.start()
                yield connection
                await transaction.commit()
            except Exception:
                await transaction.rollback()
                raise

    async def handle_error(self, error: Exception):
        """Handle database errors by wrapping them in a DatabaseError."""
        logger.error(f"Database error: {error}")
        raise DatabaseError(str(error)) from error
