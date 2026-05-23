from typing import Dict, List, Optional, Any
from app.data_access.neo4j.relationships.base_relationship_repository import BaseRelationshipRepository

class GoalRelationshipRepository(BaseRelationshipRepository):
    """
    Repository for relationships where Goal is the source node.
    """

    # Goal → Concept (BASED_ON)
    async def link_to_concept(
        self,
        goal_id: str,
        concept_id: str,
        relevance: float
    ) -> str:
        """Link a goal that is based on a concept."""
        properties = {"relevance": relevance}
        return await self._create_relationship(
            goal_id, concept_id, "Goal", "Concept", "BASED_ON", properties
        )

    async def find_based_on_concepts(self, goal_id: str) -> List[Dict[str, Any]]:
        """Find all concepts a goal is based on."""
        query = """
        MATCH (g:Goal {id: $goal_id})-[r:BASED_ON]->(c:Concept)
        RETURN c, r
        ORDER BY r.relevance DESC
        """
        return await self._execute_read(query, {"goal_id": goal_id})

    async def find_by_concept(self, concept_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Find goals based on a specific concept."""
        return await self._find_by_relationship(
            concept_id, "Concept", "BASED_ON", "Goal", user_id, limit=100
        )
