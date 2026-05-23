from typing import Optional, Dict, Any, List
from uuid import UUID
from app.data_access.postgresql.base_repository import BasePostgreSQLRepository

class EntryThreadRepository(BasePostgreSQLRepository):
    """Repository for managing entry-thread relationships."""

    async def create(self, entry_id: UUID, thread_id: str, relation_type: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Create a new entry-thread link."""
        query = """
            INSERT INTO entry_threads (entry_id, thread_id, relation_type, user_id)
            VALUES ($1, $2, $3, $4)
            RETURNING *
        """
        return await self.fetch_one(query, entry_id, thread_id, relation_type, user_id)

    async def get_by_entry_id(self, entry_id: UUID) -> List[Dict[str, Any]]:
        """Get links by entry_id."""
        query = "SELECT * FROM entry_threads WHERE entry_id = $1"
        return await self.fetch_all(query, entry_id)

    async def get_by_thread_id(self, thread_id: str) -> List[Dict[str, Any]]:
        """Get links by thread_id."""
        query = "SELECT * FROM entry_threads WHERE thread_id = $1"
        return await self.fetch_all(query, thread_id)

    async def delete(self, id: UUID) -> bool:
        """Delete a link."""
        query = "DELETE FROM entry_threads WHERE id = $1"
        result = await self.execute(query, id)
        return "DELETE 0" not in result
