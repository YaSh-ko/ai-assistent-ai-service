import logging
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from app.models.chat_session import ChatSession, SessionStatus
from app.models.message import Message
from app.data_access.postgresql.chat_session_repository import ChatSessionRepository

logger = logging.getLogger(__name__)

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
    async def get_history(self, session_id: str, limit: int = 20, offset: int = 0) -> List[Message]:
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

class SessionManager(ISessionManager):
    """
    Implementation of SessionManager.
    Manages chat sessions using PostgreSQL for persistence and in-memory cache for active sessions.
    """

    def __init__(self, repository: ChatSessionRepository):
        self.repository = repository
        self._cache: Dict[str, ChatSession] = {}
        self._cache_ttl = timedelta(minutes=30)  # Cache TTL

    async def create_session(self, user_id: str) -> ChatSession:
        """Create a new chat session."""
        import uuid
        session_id = str(uuid.uuid4())
        
        logger.info(f"Creating new session {session_id} for user {user_id}")
        
        data = await self.repository.create(user_id, session_id)
        if not data:
            raise RuntimeError("Failed to create session in database")
            
        session = ChatSession(**data)
        self._cache_session(session)
        return session

    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get session by ID, checking cache first."""
        # 1. Check cache
        if session_id in self._cache:
            session = self._cache[session_id]
            return session
            
        # 2. Fetch from DB
        data = await self.repository.get_by_id(session_id)
        if data:
            session = ChatSession(**data)
            self._cache_session(session)
            return session
            
        return None

    async def update_session(self, session_id: str, data: Dict[str, Any]) -> Optional[ChatSession]:
        """Update session data."""
        updated_data = await self.repository.update(session_id, data)
        if updated_data:
            session = ChatSession(**updated_data)
            self._cache_session(session)
            return session
        return None

    async def save_message(self, session_id: str, role: str, content: str) -> Message:
        """Save a message to the session history."""
        message = Message(role=role, content=content)
        
        # Save to DB
        await self.repository.add_message(session_id, message.model_dump())
        
        if session_id in self._cache:
            self._cache[session_id].last_active_at = datetime.now()
            
        return message

    async def get_history(self, session_id: str, limit: int = 20, offset: int = 0) -> List[Message]:
        """Get message history with pagination."""
        history_data = await self.repository.get_history(session_id, limit, offset)
        return [Message(**msg) for msg in history_data]

    async def close_session(self, session_id: str) -> bool:
        """Close a session."""
        logger.info(f"Closing session {session_id}")
        session = await self.get_session(session_id)
        if not session:
            return False
        meta = dict(session.metadata or {})
        meta["status"] = SessionStatus.CLOSED.value
        updated = await self.update_session(session_id, {"metadata": meta})
        
        # Remove from cache
        if session_id in self._cache:
            del self._cache[session_id]
            
        return updated is not None

    async def validate_session(self, session_id: str) -> bool:
        """Check if session is valid and active."""
        session = await self.get_session(session_id)
        if not session:
            return False
        return session.status == SessionStatus.ACTIVE or session.status == "active"

    def _cache_session(self, session: ChatSession):
        """Helper to cache session."""
        self._cache[session.thread_id] = session
