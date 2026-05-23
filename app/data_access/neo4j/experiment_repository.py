from typing import Dict, List, Optional, Any
from datetime import datetime
from app.data_access.repositories.base_repository import BaseGraphRepository

class ExperimentRepository(BaseGraphRepository):
    """
    Repository for Experiment nodes.
    """

    async def create_experiment(
        self,
        experiment_id: str,
        title: str,
        user_id: str,
        status: str,
        description: Optional[str] = None,
        started_at: Optional[datetime] = None,
        ended_at: Optional[datetime] = None,
        outcome: Optional[str] = None,
        success: Optional[int] = None
    ) -> str:
        """
        Create a new Experiment node.
        """
        query = """
        CREATE (e:Experiment {
            id: $experiment_id,
            title: $title,
            user_id: $user_id,
            status: $status,
            description: $description,
            started_at: datetime($started_at),
            ended_at: datetime($ended_at),
            outcome: $outcome,
            success: $success,
            created_at: datetime(),
            updated_at: datetime()
        })
        RETURN e.id as id
        """
        params = {
            "experiment_id": experiment_id,
            "title": title,
            "user_id": user_id,
            "status": status,
            "description": description,
            "started_at": self._format_datetime(started_at),
            "ended_at": self._format_datetime(ended_at),
            "outcome": outcome,
            "success": success
        }
        await self._execute_write(query, params)
        return experiment_id

    async def get_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an Experiment by ID.
        """
        query = """
        MATCH (e:Experiment {id: $experiment_id})
        RETURN e
        """
        result = await self._execute_read(query, {"experiment_id": experiment_id})
        if result:
            return result[0]["e"]
        return None

    async def update_experiment(self, experiment_id: str, properties: Dict[str, Any]) -> bool:
        """
        Update an Experiment's properties.
        """
        set_clauses = []
        params = {"experiment_id": experiment_id}
        for key, value in properties.items():
            set_clauses.append(f"e.{key} = ${key}")
            params[key] = value
        
        if not set_clauses:
            return False

        set_clauses.append("e.updated_at = datetime()")
        set_query = ", ".join(set_clauses)

        query = f"""
        MATCH (e:Experiment {{id: $experiment_id}})
        SET {set_query}
        """
        result = await self._execute_write(query, params)
        return result.get("properties_set", 0) > 0

    async def delete_experiment(self, experiment_id: str) -> bool:
        """
        Delete an Experiment.
        """
        query = """
        MATCH (e:Experiment {id: $experiment_id})
        DETACH DELETE e
        """
        result = await self._execute_write(query, {"experiment_id": experiment_id})
        return result.get("nodes_deleted", 0) > 0

    async def find_by_user(self, user_id: str, status: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find experiments by user ID, optionally filtered by status.
        """
        where_clause = "e.user_id = $user_id"
        params = {"user_id": user_id, "limit": limit}
        
        if status:
            where_clause += " AND e.status = $status"
            params["status"] = status

        query = f"""
        MATCH (e:Experiment)
        WHERE {where_clause}
        RETURN e
        ORDER BY e.created_at DESC
        LIMIT $limit
        """
        result = await self._execute_read(query, params)
        return [record["e"] for record in result]

    async def find_active(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Find active experiments for a user.
        """
        return await self.find_by_user(user_id, status="active", limit=100)

    async def complete_experiment(
        self,
        experiment_id: str,
        outcome: str,
        success: int,
        ended_at: datetime
    ) -> bool:
        """
        Mark an experiment as completed.
        """
        properties = {
            "status": "completed",
            "outcome": outcome,
            "success": success,
            "ended_at": self._format_datetime(ended_at)
        }
        return await self.update_experiment(experiment_id, properties)
