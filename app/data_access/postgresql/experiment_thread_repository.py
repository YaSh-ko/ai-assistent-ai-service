from typing import Optional, Dict, Any, List
from uuid import UUID
from app.data_access.postgresql.base_repository import BasePostgreSQLRepository

class ExperimentThreadRepository(BasePostgreSQLRepository):
    """Repository for managing experiment-thread relationships."""

    async def create(self, experiment_id: UUID, thread_id: str, relation_type: str) -> Optional[Dict[str, Any]]:
        """Create a new experiment-thread link."""
        query = """
            INSERT INTO experiment_threads (experiment_id, thread_id, relation_type)
            VALUES ($1, $2, $3)
            RETURNING *
        """
        return await self.fetch_one(query, experiment_id, thread_id, relation_type)

    async def get_by_experiment_id(self, experiment_id: UUID) -> List[Dict[str, Any]]:
        """Get links by experiment_id."""
        query = "SELECT * FROM experiment_threads WHERE experiment_id = $1"
        return await self.fetch_all(query, experiment_id)

    async def get_by_thread_id(self, thread_id: str) -> List[Dict[str, Any]]:
        """Get links by thread_id."""
        query = "SELECT * FROM experiment_threads WHERE thread_id = $1"
        return await self.fetch_all(query, thread_id)

    async def delete(self, id: UUID) -> bool:
        """Delete a link."""
        query = "DELETE FROM experiment_threads WHERE id = $1"
        result = await self.execute(query, id)
        return "DELETE 0" not in result
