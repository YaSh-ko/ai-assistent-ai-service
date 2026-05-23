from typing import Dict, List, Optional, Any
from app.data_access.neo4j.relationships.base_relationship_repository import BaseRelationshipRepository

class ExperimentRelationshipRepository(BaseRelationshipRepository):
    """
    Repository for relationships where Experiment is the source node.
    """

    # Experiment → Concept (TESTS)
    async def link_to_concept(
        self,
        experiment_id: str,
        concept_id: str,
        hypothesis_strength: float,
        validation_status: Optional[str] = None
    ) -> str:
        """Link an experiment that tests a concept."""
        properties = {
            "hypothesis_strength": hypothesis_strength,
            "validation_status": validation_status or "pending"
        }
        return await self._create_relationship(
            experiment_id, concept_id, "Experiment", "Concept", "TESTS", properties
        )

    async def find_tested_concepts(self, experiment_id: str) -> List[Dict[str, Any]]:
        """Find all concepts tested by an experiment."""
        query = """
        MATCH (exp:Experiment {id: $experiment_id})-[r:TESTS]->(c:Concept)
        RETURN c, r
        ORDER BY r.hypothesis_strength DESC
        """
        return await self._execute_read(query, {"experiment_id": experiment_id})

    # Experiment → Goal (SUPPORTS)
    async def link_to_goal(
        self,
        experiment_id: str,
        goal_id: str,
        contribution: Optional[float] = None
    ) -> str:
        """Link an experiment that supports a goal."""
        properties = {"contribution": contribution} if contribution else {}
        return await self._create_relationship(
            experiment_id, goal_id, "Experiment", "Goal", "SUPPORTS", properties
        )

    async def find_supported_goals(self, experiment_id: str) -> List[Dict[str, Any]]:
        """Find all goals supported by an experiment."""
        query = """
        MATCH (exp:Experiment {id: $experiment_id})-[r:SUPPORTS]->(g:Goal)
        RETURN g, r
        ORDER BY r.contribution DESC
        """
        return await self._execute_read(query, {"experiment_id": experiment_id})
