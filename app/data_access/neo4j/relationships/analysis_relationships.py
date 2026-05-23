from typing import Dict, List, Optional, Any
from datetime import datetime
from app.data_access.neo4j.relationships.base_relationship_repository import BaseRelationshipRepository

class AnalysisRelationshipRepository(BaseRelationshipRepository):
    """
    Repository for relationships where Analysis is the source node.
    """

    # Analysis → Concept (PRODUCES)
    async def link_to_concept(
        self,
        analysis_id: str,
        concept_id: str,
        emerged_at: Optional[datetime] = None,
        confidence: Optional[float] = None
    ) -> str:
        """Link an analysis that produces a concept."""
        properties = {
            "emerged_at": self._format_datetime(emerged_at or datetime.now()),
            "confidence": confidence
        }
        return await self._create_relationship(
            analysis_id, concept_id, "Analysis", "Concept", "PRODUCES", properties
        )

    async def find_produced_concepts(self, analysis_id: str) -> List[Dict[str, Any]]:
        """Find all concepts produced by an analysis."""
        query = """
        MATCH (a:Analysis {id: $analysis_id})-[r:PRODUCES]->(c:Concept)
        RETURN c, r
        ORDER BY r.emerged_at DESC
        """
        return await self._execute_read(query, {"analysis_id": analysis_id})

    # Analysis → Goal (LEADS_TO)
    async def link_to_goal(
        self,
        analysis_id: str,
        goal_id: str,
        emerged_at: Optional[datetime] = None,
        motivation: Optional[str] = None
    ) -> str:
        """Link an analysis that leads to a goal."""
        properties = {
            "emerged_at": self._format_datetime(emerged_at or datetime.now()),
            "motivation": motivation
        }
        return await self._create_relationship(
            analysis_id, goal_id, "Analysis", "Goal", "LEADS_TO", properties
        )

    async def find_resulting_goals(self, analysis_id: str) -> List[Dict[str, Any]]:
        """Find all goals resulting from an analysis."""
        query = """
        MATCH (a:Analysis {id: $analysis_id})-[r:LEADS_TO]->(g:Goal)
        RETURN g, r
        ORDER BY r.emerged_at DESC
        """
        return await self._execute_read(query, {"analysis_id": analysis_id})

    # Analysis → Experiment (LEADS_TO)
    async def link_to_experiment(
        self,
        analysis_id: str,
        experiment_id: str,
        emerged_at: Optional[datetime] = None,
        hypothesis: Optional[str] = None
    ) -> str:
        """Link an analysis that leads to an experiment."""
        properties = {
            "emerged_at": self._format_datetime(emerged_at or datetime.now()),
            "hypothesis": hypothesis
        }
        return await self._create_relationship(
            analysis_id, experiment_id, "Analysis", "Experiment", "LEADS_TO", properties
        )

    # Analysis → Event (ANALYZES)
    async def link_to_event(
        self,
        analysis_id: str,
        event_id: str,
        depth: Optional[str] = None
    ) -> str:
        """Link an analysis that analyzes an event."""
        properties = {"depth": depth} if depth else {}
        return await self._create_relationship(
            analysis_id, event_id, "Analysis", "Event", "ANALYZES", properties
        )
