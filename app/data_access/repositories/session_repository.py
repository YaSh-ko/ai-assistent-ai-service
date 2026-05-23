from typing import Any, Dict, Optional
from app.data_access.repositories.base_repository import BaseRepository


class SessionRepository(BaseRepository):
    """In-memory stub repository for managing sessions.

    Concrete persistence is handled by
    app.data_access.postgresql.session_repository.SessionRepository.
    This class exists as a base stub; subclass and override methods
    to add real storage behaviour.
    """

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return session by ID. Override in subclass for real storage."""
        pass

    async def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Persist a new session. Override in subclass for real storage."""
        pass

    async def update_session(self, session_id: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing session. Override in subclass for real storage."""
        pass

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session. Override in subclass for real storage."""
        pass
