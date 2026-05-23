from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class ISessionRepository(ABC):
    """Interface for session repository."""

    @abstractmethod
    async def create(self, user_id: str, thread_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """Create a new session."""
        pass

    @abstractmethod
    async def get_by_id(self, id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID."""
        pass

    @abstractmethod
    async def get_by_thread_id(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get session by thread_id."""
        pass

    @abstractmethod
    async def get_by_session_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by session_id."""
        pass

    @abstractmethod
    async def update_last_active(self, id: str) -> Optional[Dict[str, Any]]:
        """Update last_active_at timestamp."""
        pass

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """Delete a session."""
        pass
