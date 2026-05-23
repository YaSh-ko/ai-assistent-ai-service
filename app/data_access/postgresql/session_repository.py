from typing import Optional, Dict, Any
from datetime import datetime
from app.data_access.postgresql.base_repository import BasePostgreSQLRepository
from app.interfaces.repositories.i_session_repository import ISessionRepository

class SessionRepository(BasePostgreSQLRepository, ISessionRepository):
    """Repository for managing user sessions."""

    async def create(self, user_id: str, thread_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """Create a new session."""
        query = """
            INSERT INTO gigachat_sessions (user_id, thread_id, session_id)
            VALUES ($1, $2, $3)
            RETURNING *
        """
        return await self.fetch_one(query, user_id, thread_id, session_id)

    async def get_by_id(self, id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID."""
        query = "SELECT * FROM gigachat_sessions WHERE id = $1"
        return await self.fetch_one(query, id)

    async def get_by_thread_id(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get session by thread_id."""
        query = "SELECT * FROM gigachat_sessions WHERE thread_id = $1"
        return await self.fetch_one(query, thread_id)

    async def get_by_session_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by session_id."""
        query = "SELECT * FROM gigachat_sessions WHERE session_id = $1"
        return await self.fetch_one(query, session_id)

    async def update_last_active(self, id: str) -> Optional[Dict[str, Any]]:
        """Update last_active_at timestamp."""
        query = """
            UPDATE gigachat_sessions
            SET last_active_at = CURRENT_TIMESTAMP
            WHERE id = $1
            RETURNING *
        """
        return await self.fetch_one(query, id)

    async def delete(self, id: str) -> bool:
        """Delete a session."""
        query = "DELETE FROM gigachat_sessions WHERE id = $1"
        result = await self.execute(query, id)
        # result is usually "DELETE 1" or similar
        return "DELETE 0" not in result
