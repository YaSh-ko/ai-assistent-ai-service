from typing import Any, Dict, List, Optional, Generic, TypeVar
from app.core.interfaces.i_graph_database import IGraphDatabase
from datetime import datetime

T = TypeVar("T")

class BaseRepository(Generic[T]):
    """Base repository class."""
    
    def __init__(self, database: Any):
        self.database = database

    async def get(self, id: Any) -> Optional[T]:
        raise NotImplementedError

    async def create(self, item: T) -> T:
        raise NotImplementedError

    async def update(self, id: Any, item: T) -> T:
        raise NotImplementedError

    async def delete(self, id: Any) -> bool:
        raise NotImplementedError

    async def commit(self):
        """Commit current transaction (if the driver supports it)."""
        raise NotImplementedError

    async def rollback(self):
        """Rollback current transaction."""
        raise NotImplementedError

class BaseGraphRepository:
    """
    Abstract base class for graph repositories.
    """
    def __init__(self, db: IGraphDatabase):
        self.db = db

    async def _execute_read(self, query: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute a read query.
        """
        return await self.db.execute_read(query, params)

    async def _execute_write(self, query: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a write query.
        """
        return await self.db.execute_write(query, params)
    
    def _format_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """
        Format datetime to ISO format string for Neo4j.
        """
        if dt:
            return dt.isoformat()
        return None
