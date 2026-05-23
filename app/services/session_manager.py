import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from app.interfaces.services.i_session_manager import ISessionManager
from app.models.chat_session import ChatSession, SessionStatus
from app.models.message import Message
from app.data_access.postgresql.chat_session_repository import ChatSessionRepository

logger = logging.getLogger(__name__)

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
        thread_id = str(uuid.uuid4())
        
        logger.info(f"Creating new session {thread_id} for user {user_id}")
        
        data = await self.repository.create(user_id, thread_id)
        if not data:
            raise RuntimeError("Failed to create session in database")
            
        session = ChatSession(**data)
        self._cache_session(session)
        return session

    async def get_session(self, thread_id: str) -> Optional[ChatSession]:
        """Get session by ID, checking cache first."""
        # 1. Check cache
        if thread_id in self._cache:
            session = self._cache[thread_id]
            return session
            
        # 2. Fetch from DB
        data = await self.repository.get_by_id(thread_id)
        if data:
            session = ChatSession(**data)
            self._cache_session(session)
            return session
            
        return None

    async def update_session(self, thread_id: str, data: Dict[str, Any]) -> Optional[ChatSession]:
        """Update session data."""
        updated_data = await self.repository.update(thread_id, data)
        if updated_data:
            session = ChatSession(**updated_data)
            self._cache_session(session)
            return session
        return None

    async def save_message(self, thread_id: str, role: str, content: str) -> Message:
        """Save a message to the session history."""
        message = Message(role=role, content=content)
        
        # Save to DB
        await self.repository.add_message(thread_id, message.model_dump())
        
        # Invalidate cache to force reload from DB on next get
        if thread_id in self._cache:
            del self._cache[thread_id]
            
        return message

    async def get_history(self, thread_id: str, limit: int = 20, offset: int = 0) -> List[Message]:
        """Get message history with pagination."""
        history_data = await self.repository.get_history(thread_id, limit, offset)
        return [Message(**msg) for msg in history_data]

    async def save_thread_state(
        self, thread_id: str, run_id: str, assistant_id: Optional[str],
        final_messages: list, parent_checkpoint_id: Optional[str] = None
    ) -> Optional[str]:
        """Save run result as a checkpoint state. Returns new checkpoint_id."""
        import uuid
        from datetime import datetime, timezone

        MAX_STATES = 10  # keep last 10 checkpoints to prevent unbounded growth

        session = await self.get_session(thread_id)
        if not session:
            return None

        checkpoint_id = str(uuid.uuid4())

        if parent_checkpoint_id:
            parent_cp = {"thread_id": thread_id, "checkpoint_ns": "", "checkpoint_id": parent_checkpoint_id}
        elif session.states:
            parent_cp = session.states[0]["checkpoint"]
        else:
            parent_cp = None

        history_entry = {
            "values": {"messages": final_messages},
            "next": [],
            "checkpoint": {
                "thread_id": thread_id,
                "checkpoint_ns": "",
                "checkpoint_id": checkpoint_id,
            },
            "parent_checkpoint": parent_cp,
            "metadata": {
                "run_id": run_id,
                "assistant_id": assistant_id,
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tasks": [],
        }

        new_states = ([history_entry] + (session.states or []))[:MAX_STATES]
        await self.update_session(thread_id, {
            "states": new_states,
            "history": final_messages,
        })
        return checkpoint_id

    async def get_messages_by_checkpoint(self, thread_id: str, checkpoint_id: str) -> list:
        """Get messages for a specific checkpoint from states."""
        session = await self.get_session(thread_id)
        if not session or not session.states:
            return []
            
        for state in session.states:
            cp = state.get("checkpoint", {})
            if cp.get("checkpoint_id") == checkpoint_id:
                return state.get("values", {}).get("messages", [])
        
        # Fallback to current history if not found in states
        return session.history or []

    async def close_session(self, thread_id: str) -> bool:
        """Close a session."""
        logger.info(f"Closing session {thread_id}")
        session = await self.get_session(thread_id)
        if not session:
            return False
        meta = dict(session.metadata or {})
        meta["status"] = SessionStatus.CLOSED.value
        updated = await self.update_session(thread_id, {"metadata": meta})
        
        # Remove from cache
        if thread_id in self._cache:
            del self._cache[thread_id]
            
        return updated is not None

    async def validate_session(self, thread_id: str) -> bool:
        """Check if session is valid and active."""
        session = await self.get_session(thread_id)
        if not session:
            return False
        return session.status == SessionStatus.ACTIVE or session.status == "active"

    def _cache_session(self, session: ChatSession):
        """Helper to cache session."""
        self._cache[session.thread_id] = session
        # In a real app, we'd have a background task to clean up old cache entries
