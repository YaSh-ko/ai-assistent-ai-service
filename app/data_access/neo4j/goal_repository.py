from typing import Dict, List, Optional, Any
from datetime import datetime
from app.data_access.repositories.base_repository import BaseGraphRepository

class GoalRepository(BaseGraphRepository):
    """
    Repository for Goal nodes.
    """

    async def create_goal(
        self,
        goal_id: str,
        title: str,
        user_id: str,
        status: str,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        target_date: Optional[datetime] = None
    ) -> str:
        """
        Create a new Goal node.
        """
        query = """
        CREATE (g:Goal {
            id: $goal_id,
            title: $title,
            user_id: $user_id,
            status: $status,
            description: $description,
            priority: $priority,
            target_date: datetime($target_date),
            created_at: datetime(),
            updated_at: datetime()
        })
        RETURN g.id as id
        """
        params = {
            "goal_id": goal_id,
            "title": title,
            "user_id": user_id,
            "status": status,
            "description": description,
            "priority": priority,
            "target_date": self._format_datetime(target_date)
        }
        await self._execute_write(query, params)
        return goal_id

    async def get_goal(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a Goal by ID.
        """
        query = """
        MATCH (g:Goal {id: $goal_id})
        RETURN g
        """
        result = await self._execute_read(query, {"goal_id": goal_id})
        if result:
            return result[0]["g"]
        return None

    async def update_goal(self, goal_id: str, properties: Dict[str, Any]) -> bool:
        """
        Update a Goal's properties.
        """
        set_clauses = []
        params = {"goal_id": goal_id}
        for key, value in properties.items():
            set_clauses.append(f"g.{key} = ${key}")
            params[key] = value
        
        if not set_clauses:
            return False

        set_clauses.append("g.updated_at = datetime()")
        set_query = ", ".join(set_clauses)

        query = f"""
        MATCH (g:Goal {{id: $goal_id}})
        SET {set_query}
        """
        result = await self._execute_write(query, params)
        return result.get("properties_set", 0) > 0

    async def delete_goal(self, goal_id: str) -> bool:
        """
        Delete a Goal.
        """
        query = """
        MATCH (g:Goal {id: $goal_id})
        DETACH DELETE g
        """
        result = await self._execute_write(query, {"goal_id": goal_id})
        return result.get("nodes_deleted", 0) > 0

    async def find_by_user(self, user_id: str, status: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find goals by user ID, optionally filtered by status.
        """
        where_clause = "g.user_id = $user_id"
        params = {"user_id": user_id, "limit": limit}
        
        if status:
            where_clause += " AND g.status = $status"
            params["status"] = status

        query = f"""
        MATCH (g:Goal)
        WHERE {where_clause}
        RETURN g
        ORDER BY g.created_at DESC
        LIMIT $limit
        """
        result = await self._execute_read(query, params)
        return [record["g"] for record in result]

    async def find_by_priority(self, user_id: str, priority: str) -> List[Dict[str, Any]]:
        """
        Find goals by user ID and priority.
        """
        query = """
        MATCH (g:Goal {user_id: $user_id, priority: $priority})
        RETURN g
        ORDER BY g.created_at DESC
        """
        result = await self._execute_read(query, {"user_id": user_id, "priority": priority})
        return [record["g"] for record in result]
