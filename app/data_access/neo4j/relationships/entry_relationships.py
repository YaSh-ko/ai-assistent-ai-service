from typing import Dict, List, Optional, Any
from datetime import datetime
from app.data_access.neo4j.relationships.base_relationship_repository import BaseRelationshipRepository

class EntryRelationshipRepository(BaseRelationshipRepository):
    """
    Repository for relationships where Entry is the source node.
    """

    # Entry → Concept (MENTIONS)
    async def link_to_concept(
        self,
        entry_id: str,
        concept_id: str,
        context: str,
        relevance: float,
        mentioned_at: Optional[datetime] = None
    ) -> str:
        """Link an entry to a concept."""
        properties = {
            "context": context,
            "relevance": relevance,
            "mentioned_at": self._format_datetime(mentioned_at or datetime.now())
        }
        return await self._create_relationship(
            entry_id, concept_id, "Entry", "Concept", "MENTIONS", properties
        )

    async def find_by_concept(self, concept_id: str, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Find entries that mention a specific concept."""
        return await self._find_by_relationship(
            concept_id, "Concept", "MENTIONS", "Entry", user_id, limit
        )

    # Entry → Affect (EXPRESSES)
    async def link_to_affect(
        self,
        entry_id: str,
        affect_id: str,
        intensity: float,
        context: Optional[str] = None,
        expressed_at: Optional[datetime] = None
    ) -> str:
        """Link an entry to an affect."""
        properties = {
            "intensity": intensity,
            "context": context,
            "expressed_at": self._format_datetime(expressed_at or datetime.now())
        }
        return await self._create_relationship(
            entry_id, affect_id, "Entry", "Affect", "EXPRESSES", properties
        )

    async def find_by_affect(self, affect_id: str, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Find entries that express a specific affect."""
        return await self._find_by_relationship(
            affect_id, "Affect", "EXPRESSES", "Entry", user_id, limit
        )

    # Entry → Event (DESCRIBES)
    async def link_to_event(
        self,
        entry_id: str,
        event_id: str,
        sentiment: float,
        perspective: str,
        context: str
    ) -> str:
        """Link an entry to an event."""
        properties = {
            "sentiment": sentiment,
            "perspective": perspective,
            "context": context
        }
        return await self._create_relationship(
            entry_id, event_id, "Entry", "Event", "DESCRIBES", properties
        )

    async def find_by_event(self, event_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Find entries that describe a specific event."""
        return await self._find_by_relationship(
            event_id, "Event", "DESCRIBES", "Entry", user_id, limit=100
        )

    # Entry → Goal (RELATES_TO)
    async def link_to_goal(
        self,
        entry_id: str,
        goal_id: str,
        relation_type: str,
        sentiment: float,
        context: Optional[str] = None
    ) -> str:
        """Link an entry to a goal."""
        properties = {
            "relation_type": relation_type,
            "sentiment": sentiment,
            "context": context
        }
        return await self._create_relationship(
            entry_id, goal_id, "Entry", "Goal", "RELATES_TO", properties
        )

    async def get_goal_progress_chain(self, goal_id: str) -> List[Dict[str, Any]]:
        """Get all entries related to a goal, ordered by time."""
        query = """
        MATCH (e:Entry)-[r:RELATES_TO]->(g:Goal {id: $goal_id})
        RETURN e, r
        ORDER BY e.timestamp ASC
        """
        return await self._execute_read(query, {"goal_id": goal_id})

    # Entry → Experiment (DOCUMENTS)
    async def link_to_experiment(
        self,
        entry_id: str,
        experiment_id: str,
        day_number: Optional[int],
        observation: str,
        sentiment: Optional[float] = None
    ) -> str:
        """Link an entry to an experiment."""
        properties = {
            "day_number": day_number,
            "observation": observation,
            "sentiment": sentiment
        }
        return await self._create_relationship(
            entry_id, experiment_id, "Entry", "Experiment", "DOCUMENTS", properties
        )

    async def get_experiment_journal(self, experiment_id: str) -> List[Dict[str, Any]]:
        """Get all entries documenting an experiment, ordered by day."""
        query = """
        MATCH (e:Entry)-[r:DOCUMENTS]->(exp:Experiment {id: $experiment_id})
        RETURN e, r
        ORDER BY r.day_number ASC
        """
        return await self._execute_read(query, {"experiment_id": experiment_id})

    # Entry → Analysis (CONTAINS_ANALYSIS)
    async def link_to_analysis(self, entry_id: str, analysis_id: str) -> str:
        """Link an entry to an analysis."""
        return await self._create_relationship(
            entry_id, analysis_id, "Entry", "Analysis", "CONTAINS_ANALYSIS", {}
        )

    # Entry → Entry (FOLLOWS)
    async def link_follows(self, from_entry_id: str, to_entry_id: str, time_gap_minutes: Optional[int] = None) -> str:
        """Link two entries in sequence."""
        properties = {"time_gap_minutes": time_gap_minutes} if time_gap_minutes else {}
        return await self._create_relationship(
            from_entry_id, to_entry_id, "Entry", "Entry", "FOLLOWS", properties
        )

    async def find_connected_entries(self, entry_id: str, depth: int = 2) -> List[Dict[str, Any]]:
        """Find entries connected via FOLLOWS relationship."""
        query = f"""
        MATCH path = (e:Entry {{id: $entry_id}})-[:FOLLOWS*1..{depth}]-(connected:Entry)
        RETURN connected, length(path) as distance
        ORDER BY distance ASC
        """
        return await self._execute_read(query, {"entry_id": entry_id})

    # Entry → Concept (IMPACTS)
    async def link_impacts_concept(
        self,
        entry_id: str,
        concept_id: str,
        impact_text: str,
        intensity: int,
        created_at: Optional[datetime] = None
    ) -> str:
        """Link an entry that impacts a concept."""
        properties = {
            "impact_text": impact_text,
            "intensity": intensity,
            "created_at": self._format_datetime(created_at or datetime.now())
        }
        return await self._create_relationship(
            entry_id, concept_id, "Entry", "Concept", "IMPACTS", properties
        )
