from typing import Dict, List, Optional, Any
from datetime import datetime
from app.data_access.neo4j.relationships.base_relationship_repository import BaseRelationshipRepository

class ConceptRelationshipRepository(BaseRelationshipRepository):
    """
    Repository for relationships where Concept is the source node.
    """

    # Concept → Concept (EVOLVES_INTO)
    async def link_evolution(
        self,
        from_concept_id: str,
        to_concept_id: str,
        evolution_type: str,
        evolved_at: Optional[datetime] = None,
        description: Optional[str] = None
    ) -> str:
        """Link concept evolution."""
        properties = {
            "evolution_type": evolution_type,
            "evolved_at": self._format_datetime(evolved_at or datetime.now()),
            "description": description
        }
        return await self._create_relationship(
            from_concept_id, to_concept_id, "Concept", "Concept", "EVOLVES_INTO", properties
        )

    async def get_evolution_chain(self, concept_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Get the evolution chain of a concept."""
        query = """
        MATCH path = (c:Concept {id: $concept_id, user_id: $user_id})-[:EVOLVES_INTO*]->(evolved:Concept)
        RETURN evolved, length(path) as depth
        ORDER BY depth ASC
        """
        return await self._execute_read(query, {"concept_id": concept_id, "user_id": user_id})

    # Concept → Experiment (INSPIRES)
    async def link_inspires_experiment(
        self,
        concept_id: str,
        experiment_id: str,
        inspired_at: Optional[datetime] = None
    ) -> str:
        """Link a concept that inspires an experiment."""
        properties = {
            "inspired_at": self._format_datetime(inspired_at or datetime.now())
        }
        return await self._create_relationship(
            concept_id, experiment_id, "Concept", "Experiment", "INSPIRES", properties
        )

    async def find_inspired_experiments(self, concept_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Find all experiments inspired by a concept."""
        query = """
        MATCH (c:Concept {id: $concept_id})-[r:INSPIRES]->(exp:Experiment)
        WHERE exp.user_id = $user_id
        RETURN exp, r
        ORDER BY r.inspired_at DESC
        """
        return await self._execute_read(query, {"concept_id": concept_id, "user_id": user_id})
