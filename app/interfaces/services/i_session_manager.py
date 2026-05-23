from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from app.models.chat_session import ChatSession
from app.models.message import Message

class ISessionManager(ABC):
    """Interface for managing user chat sessions."""

    @abstractmethod
    async def create_session(self, user_id: str) -> ChatSession:
        """Create a new chat session for a user."""
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get a chat session by ID."""
        pass

    @abstractmethod
    async def update_session(self, session_id: str, data: Dict[str, Any]) -> Optional[ChatSession]:
        """Update session data (status, context, etc.)."""
        pass

    @abstractmethod
    async def save_message(self, session_id: str, role: str, content: str) -> Message:
        """Save a message to the session history."""
        pass

    @abstractmethod
    async def get_history(self, session_id: str, limit: int = 20) -> List[Message]:
        """Get message history for a session."""
        pass

    @abstractmethod
    async def close_session(self, session_id: str) -> bool:
        """Close a session (mark as closed)."""
        pass

    @abstractmethod
    async def validate_session(self, session_id: str) -> bool:
        """Check if a session is valid and active."""
        pass
