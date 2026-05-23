from typing import Dict, List, Optional, Any
from app.data_access.repositories.base_repository import BaseGraphRepository

class ConceptRepository(BaseGraphRepository):
    """
    Repository for Concept nodes.
    """

    async def create_concept(
        self,
        concept_id: str,
        name: str,
        user_id: str,
        description: str,
        relevance: float
    ) -> str:
        """
        Create a new Concept node.
        """
        query = """
        CREATE (c:Concept {
            id: $concept_id,
            name: $name,
            user_id: $user_id,
            description: $description,
            relevance: $relevance,
            created_at: datetime(),
            updated_at: datetime()
        })
        RETURN c.id as id
        """
        params = {
            "concept_id": concept_id,
            "name": name,
            "user_id": user_id,
            "description": description,
            "relevance": relevance
        }
        await self._execute_write(query, params)
        return concept_id

    async def get_concept(self, concept_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a Concept by ID.
        """
        query = """
        MATCH (c:Concept {id: $concept_id})
        RETURN c
        """
        result = await self._execute_read(query, {"concept_id": concept_id})
        if result:
            return result[0]["c"]
        return None

    async def get_concept_by_name(self, name: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a Concept by name and user ID.
        """
        query = """
        MATCH (c:Concept {name: $name, user_id: $user_id})
        RETURN c
        """
        result = await self._execute_read(query, {"name": name, "user_id": user_id})
        if result:
            return result[0]["c"]
        return None

    async def update_concept(self, concept_id: str, properties: Dict[str, Any]) -> bool:
        """
        Update a Concept's properties.
        """
        set_clauses = []
        params = {"concept_id": concept_id}
        for key, value in properties.items():
            set_clauses.append(f"c.{key} = ${key}")
            params[key] = value
        
        if not set_clauses:
            return False

        set_clauses.append("c.updated_at = datetime()")
        set_query = ", ".join(set_clauses)

        query = f"""
        MATCH (c:Concept {{id: $concept_id}})
        SET {set_query}
        """
        result = await self._execute_write(query, params)
        return result.get("properties_set", 0) > 0

    async def delete_concept(self, concept_id: str) -> bool:
        """
        Delete a Concept.
        """
        query = """
        MATCH (c:Concept {id: $concept_id})
        DETACH DELETE c
        """
        result = await self._execute_write(query, {"concept_id": concept_id})
        return result.get("nodes_deleted", 0) > 0

    async def find_by_user(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find concepts by user ID.
        """
        query = """
        MATCH (c:Concept {user_id: $user_id})
        RETURN c
        ORDER BY c.relevance DESC
        LIMIT $limit
        """
        result = await self._execute_read(query, {"user_id": user_id, "limit": limit})
        return [record["c"] for record in result]

    async def get_top_concepts(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get top concepts by relevance for a user.
        """
        return await self.find_by_user(user_id, limit)
