from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class IRelationalDatabase(ABC):
    """Interface for relational databases."""

    @abstractmethod
    async def execute(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> None:
        """Execute a SQL query (INSERT, UPDATE, DELETE)."""
        pass

    @abstractmethod
    async def fetch_all(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch all results from a SQL query."""
        pass

    @abstractmethod
    async def fetch_one(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Fetch a single result from a SQL query."""
        pass
