from typing import Dict, List, Optional, Any
from app.data_access.repositories.base_repository import BaseGraphRepository

class AffectRepository(BaseGraphRepository):
    """
    Repository for Affect nodes.
    """

    async def create_affect(
        self,
        affect_id: str,
        name: str,
        user_id: str,
        valence: float,
        arousal: float,
        description: Optional[str] = None
    ) -> str:
        """
        Create a new Affect node.
        """
        query = """
        CREATE (a:Affect {
            id: $affect_id,
            name: $name,
            user_id: $user_id,
            valence: $valence,
            arousal: $arousal,
            description: $description,
            created_at: datetime(),
            updated_at: datetime()
        })
        RETURN a.id as id
        """
        params = {
            "affect_id": affect_id,
            "name": name,
            "user_id": user_id,
            "valence": valence,
            "arousal": arousal,
            "description": description
        }
        await self._execute_write(query, params)
        return affect_id

    async def get_affect(self, affect_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an Affect by ID.
        """
        query = """
        MATCH (a:Affect {id: $affect_id})
        RETURN a
        """
        result = await self._execute_read(query, {"affect_id": affect_id})
        if result:
            return result[0]["a"]
        return None

    async def get_affect_by_name(self, name: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an Affect by name and user ID.
        """
        query = """
        MATCH (a:Affect {name: $name, user_id: $user_id})
        RETURN a
        """
        result = await self._execute_read(query, {"name": name, "user_id": user_id})
        if result:
            return result[0]["a"]
        return None

    async def update_affect(self, affect_id: str, properties: Dict[str, Any]) -> bool:
        """
        Update an Affect's properties.
        """
        set_clauses = []
        params = {"affect_id": affect_id}
        for key, value in properties.items():
            set_clauses.append(f"a.{key} = ${key}")
            params[key] = value
        
        if not set_clauses:
            return False

        set_clauses.append("a.updated_at = datetime()")
        set_query = ", ".join(set_clauses)

        query = f"""
        MATCH (a:Affect {{id: $affect_id}})
        SET {set_query}
        """
        result = await self._execute_write(query, params)
        return result.get("properties_set", 0) > 0

    async def delete_affect(self, affect_id: str) -> bool:
        """
        Delete an Affect.
        """
        query = """
        MATCH (a:Affect {id: $affect_id})
        DETACH DELETE a
        """
        result = await self._execute_write(query, {"affect_id": affect_id})
        return result.get("nodes_deleted", 0) > 0

    async def find_by_user(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find affects by user ID.
        """
        query = """
        MATCH (a:Affect {user_id: $user_id})
        RETURN a
        ORDER BY a.created_at DESC
        LIMIT $limit
        """
        result = await self._execute_read(query, {"user_id": user_id, "limit": limit})
        return [record["a"] for record in result]
