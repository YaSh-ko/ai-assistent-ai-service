from typing import Any, Dict, Optional

from app.interfaces.repositories.i_session_repository import ISessionRepository


class SessionService:
    """Service for managing sessions."""
    
    def __init__(self, session_repo: ISessionRepository):
        self.session_repo = session_repo

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return await self.session_repo.get_session(session_id)

    async def create_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        return await self.session_repo.create_session(session_data)