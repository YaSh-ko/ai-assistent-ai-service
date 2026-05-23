from typing import Optional, Dict, Any, List
from uuid import UUID
from app.data_access.postgresql.base_repository import BasePostgreSQLRepository

class GoalThreadRepository(BasePostgreSQLRepository):
    """Repository for managing goal-thread relationships."""

    async def create(self, goal_id: UUID, thread_id: str, relation_type: str) -> Optional[Dict[str, Any]]:
        """Create a new goal-thread link."""
        query = """
            INSERT INTO goal_threads (goal_id, thread_id, relation_type)
            VALUES ($1, $2, $3)
            RETURNING *
        """
        return await self.fetch_one(query, goal_id, thread_id, relation_type)

    async def get_by_goal_id(self, goal_id: UUID) -> List[Dict[str, Any]]:
        """Get links by goal_id."""
        query = "SELECT * FROM goal_threads WHERE goal_id = $1"
        return await self.fetch_all(query, goal_id)

    async def get_by_thread_id(self, thread_id: str) -> List[Dict[str, Any]]:
        """Get links by thread_id."""
        query = "SELECT * FROM goal_threads WHERE thread_id = $1"
        return await self.fetch_all(query, thread_id)

    async def delete(self, id: UUID) -> bool:
        """Delete a link."""
        query = "DELETE FROM goal_threads WHERE id = $1"
        result = await self.execute(query, id)
        return "DELETE 0" not in result
