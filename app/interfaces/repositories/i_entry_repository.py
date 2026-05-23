from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import date
from uuid import UUID

class IEntryRepository(ABC):
    """Interface for entry repository."""

    @abstractmethod
    async def create(self, user_id: str, title: str, description: str, event_date: date) -> Optional[Dict[str, Any]]:
        """Create a new entry."""
        pass

    @abstractmethod
    async def get_by_id(self, id: UUID) -> Optional[Dict[str, Any]]:
        """Get entry by ID."""
        pass

    @abstractmethod
    async def get_by_ids(self, ids: List[UUID]) -> List[Dict[str, Any]]:
        """Get entries by a list of IDs."""
        pass

    @abstractmethod
    async def update(self, id: UUID, description: Optional[str] = None, title: Optional[str] = None, event_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        """Update an entry."""
        pass

    @abstractmethod
    async def delete(self, id: UUID) -> bool:
        """Delete an entry."""
        pass

    @abstractmethod
    async def count_by_user(self, user_id: str) -> int:
        """Count entries by user."""
        pass
