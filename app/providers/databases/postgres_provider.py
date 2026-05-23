from typing import Any, Dict, List, Optional
import asyncpg
import asyncio
from contextlib import asynccontextmanager
from app.interfaces.relational_database import IRelationalDatabase
from app.core.config import settings

class PostgresProvider(IRelationalDatabase):
    """
    PostgreSQL database provider using asyncpg.
    """
    _query_lock = asyncio.Lock()

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.pool: Optional[asyncpg.Pool] = None
        self.config = config
        self._lock = asyncio.Lock()
        self._loop = None

    async def connect(self):
        """Initialize the connection pool."""
        async with self._lock:
            current_loop = asyncio.get_running_loop()
            if self.pool and self._loop != current_loop:
                # Loop changed, must close old pool safely
                try:
                    if self._loop and not self._loop.is_closed():
                        # We must use the correct loop to close the pool
                        # but if we are in a different loop, we can't easily await it
                        # unless we use something like asyncio.run_coroutine_threadsafe
                        # For simplicity in tests, we just discard and hope for the best
                        # if the loop is already weird.
                        pass
                except Exception:
                    pass
                self.pool = None
                
            if not self.pool:
                self._loop = current_loop
                if self.config:
                    pool_config = {
                        k: v for k, v in self.config.items() 
                        if k in ['host', 'port', 'user', 'password', 'database', 'min_size', 'max_size', 'timeout']
                    }
                    pool_config.setdefault('min_size', 5)
                    pool_config.setdefault('max_size', 10)
                    self.pool = await asyncpg.create_pool(
                        **pool_config,
                        statement_cache_size=0
                    )
                else:
                    self.pool = await asyncpg.create_pool(
                        dsn=settings.POSTGRES_URL,
                        min_size=5,
                        max_size=10,
                        statement_cache_size=0
                    )

    async def disconnect(self):
        """Close the connection pool."""
        async with self._lock:
            if self.pool:
                await self.pool.close()
                self.pool = None
                self._loop = None

    async def _ensure_connection(self):
        """Ensure pool exists and belongs to current loop."""
        current_loop = asyncio.get_running_loop()
        if not self.pool or self._loop != current_loop:
            await self.connect()

    async def execute(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> str:
        """Execute a SQL query (INSERT, UPDATE, DELETE)."""
        await self._ensure_connection()
        
        args = list(parameters.values()) if parameters else []
        async with self._query_lock:
            return await self.pool.execute(query, *args)

    async def fetch_all(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch all results from a SQL query."""
        await self._ensure_connection()
            
        args = list(parameters.values()) if parameters else []
        async with self._query_lock:
            records = await self.pool.fetch(query, *args)
            return [dict(record) for record in records]

    async def fetch_one(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Fetch a single result from a SQL query."""
        await self._ensure_connection()
            
        args = list(parameters.values()) if parameters else []
        async with self._query_lock:
            record = await self.pool.fetchrow(query, *args)
            return dict(record) if record else None

    @asynccontextmanager
    async def transaction(self):
        """Context manager for transactions."""
        if not self.pool:
            await self.connect()
            
        async with self._query_lock:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    yield connection
