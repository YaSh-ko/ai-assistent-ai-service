from typing import Dict, Any, List
from app.core.interfaces.i_graph_database import IGraphDatabase
from app.data_access.repositories.entry_repository import EntryRepository
from app.data_access.neo4j.concept_repository import ConceptRepository
from app.data_access.neo4j.affect_repository import AffectRepository
from app.data_access.neo4j.event_repository import EventRepository
from app.data_access.neo4j.goal_repository import GoalRepository
from app.data_access.neo4j.experiment_repository import ExperimentRepository
from app.data_access.neo4j.analysis_repository import AnalysisRepository
from app.data_access.neo4j.relationships.entry_relationships import EntryRelationshipRepository
from app.data_access.neo4j.relationships.analysis_relationships import AnalysisRelationshipRepository
from app.data_access.neo4j.relationships.goal_relationships import GoalRelationshipRepository
from app.data_access.neo4j.relationships.experiment_relationships import ExperimentRelationshipRepository
from app.data_access.neo4j.relationships.concept_relationships import ConceptRelationshipRepository
from app.data_access.neo4j.relationships.relationship_queries import RelationshipQueryRepository

class GraphRepository:
    """
    Facade for accessing all graph repositories.
    Provides a unified interface to node and relationship repositories.
    """

    def __init__(self, db: IGraphDatabase):
        """
        Initialize the GraphRepository with all sub-repositories.
        
        Args:
            db: Instance of IGraphDatabase
        """
        self.db = db
        
        # Node repositories
        self.entries = EntryRepository(db)
        self.concepts = ConceptRepository(db)
        self.affects = AffectRepository(db)
        self.events = EventRepository(db)
        self.goals = GoalRepository(db)
        self.experiments = ExperimentRepository(db)
        self.analyses = AnalysisRepository(db)
        
        # Relationship repositories (grouped by source node)
        self.entry_links = EntryRelationshipRepository(db)
        self.analysis_links = AnalysisRelationshipRepository(db)
        self.goal_links = GoalRelationshipRepository(db)
        self.experiment_links = ExperimentRelationshipRepository(db)
        self.concept_links = ConceptRelationshipRepository(db)
        
        # Query repository for complex queries
        self.queries = RelationshipQueryRepository(db)

    async def create_node(self, label: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a node with the given label and properties.
        """
        query = f"CREATE (n:{label} $properties) RETURN n"
        return await self.db.execute_write(query, {"properties": properties})

    async def find_nodes_by_label(self, label: str) -> list[Dict[str, Any]]:
        """
        Find all nodes with the given label.
        """
        query = f"MATCH (n:{label}) RETURN n"
        return await self.db.execute_read(query, {})

    async def create_relationship(self, from_id: int, to_id: int, rel_type: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a relationship between two nodes identified by their internal IDs.
        """
        query = f"""
        MATCH (a), (b)
        WHERE id(a) = $from_id AND id(b) = $to_id
        CREATE (a)-[r:{rel_type} $properties]->(b)
        RETURN r
        """
        return await self.db.execute_write(query, {"from_id": from_id, "to_id": to_id, "properties": properties})

    async def find_relationships(self, from_label: str, to_label: str, rel_type: str) -> list[Dict[str, Any]]:
        """
        Find relationships of a specific type between nodes of specific labels.
        """
        query = f"""
        MATCH (a:{from_label})-[r:{rel_type}]->(b:{to_label})
        RETURN r
        """
        return await self.db.execute_read(query, {})

    async def delete_node(self, node_id: int) -> Dict[str, Any]:
        """
        Delete a node by its internal ID.
        """
        query = "MATCH (n) WHERE id(n) = $node_id DETACH DELETE n"
        return await self.db.execute_write(query, {"node_id": node_id})

    async def update_node_properties(self, node_id: int, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update properties of a node identified by its internal ID.
        """
        query = "MATCH (n) WHERE id(n) = $node_id SET n += $properties"
        return await self.db.execute_write(query, {"node_id": node_id, "properties": properties})

    async def execute_custom_query(self, query: str, parameters: Dict[str, Any] = None) -> list[Dict[str, Any]]:
        """
        Execute a custom read query.
        """
        if parameters is None:
            parameters = {}
        return await self.db.execute_read(query, parameters)

    async def health_check(self) -> bool:
        """
        Check the health of the database connection.
        """
        return await self.db.health_check()

    async def get_user_graph_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get a comprehensive summary of a user's knowledge graph.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with node counts, relationship counts, and other metrics
        """
        # Get relationship summary
        relationship_summary = await self.queries.get_relationship_summary(user_id)
        
        # Get node counts (using simple queries)
        entries_count = len(await self.entries.find_by_user(user_id, limit=10000))
        concepts_count = len(await self.concepts.find_by_user(user_id, limit=10000))
        affects_count = len(await self.affects.find_by_user(user_id, limit=10000))
        events_count = len(await self.events.find_by_user(user_id, limit=10000))
        goals_count = len(await self.goals.find_by_user(user_id, limit=10000))
        experiments_count = len(await self.experiments.find_by_user(user_id, limit=10000))
        analyses_count = len(await self.analyses.find_by_user(user_id, limit=10000))
        
        # Get most connected nodes
        most_connected = await self.queries.get_most_connected_nodes(user_id, limit=5)
        
        return {
            "user_id": user_id,
            "node_counts": {
                "entries": entries_count,
                "concepts": concepts_count,
                "affects": affects_count,
                "events": events_count,
                "goals": goals_count,
                "experiments": experiments_count,
                "analyses": analyses_count,
                "total": entries_count + concepts_count + affects_count + events_count + goals_count + experiments_count + analyses_count
            },
            "relationship_counts": relationship_summary,
            "most_connected_nodes": most_connected
        }

    async def graph_search(
        self, 
        user_id: str, 
        query_concepts: List[str], 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for entries connected to given concepts.
        
        Args:
            user_id: User ID to filter by.
            query_concepts: List of concept names to search for.
            limit: Maximum number of results.
            
        Returns:
            List of entries ordered by relevance (number of matching concepts).
        """
        if not query_concepts:
            return []
            
        # Cypher query to find entries connected to concepts
        query = """
        MATCH (e:Entry {user_id: $user_id})-[r:HAS_CONCEPT|RELATES_TO]->(c:Concept)
        WHERE c.name IN $concepts
        WITH e, COUNT(DISTINCT c) as concept_matches, COLLECT(c.name) as matched_concepts
        RETURN e, concept_matches, matched_concepts
        ORDER BY concept_matches DESC
        LIMIT $limit
        """
        
        results = await self.db.execute_read(query, {
            "user_id": user_id,
            "concepts": query_concepts,
            "limit": limit
        })
        
        # Format results
        formatted = []
        for record in results:
            entry_data = record.get('e', {})
            formatted.append({
                "id": entry_data.get('id'),
                "title": entry_data.get('title'),
                "description": entry_data.get('description'),
                "event_date": entry_data.get('event_date'),
                "graph_score": record.get('concept_matches', 0),
                "matched_concepts": record.get('matched_concepts', []),
                "source": "graph"
            })
        
        return formatted

    async def find_related_entries(
        self, 
        entry_ids: List[str], 
        depth: int = 2, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find entries related to given entries through graph traversal.
        
        Args:
            entry_ids: List of entry IDs to start from.
            depth: Maximum traversal depth.
            limit: Maximum number of results.
            
        Returns:
            List of related entries with relationship info.
        """
        if not entry_ids:
            return []
            
        # Cypher query to find related entries through multiple hops
        query = f"""
        MATCH (e1:Entry)-[r*1..{depth}]-(e2:Entry)
        WHERE e1.id IN $entry_ids AND e2.id NOT IN $entry_ids
        WITH e2, COUNT(*) as path_count, COLLECT(DISTINCT type(r[0])) as relationship_types
        RETURN e2, path_count, relationship_types
        ORDER BY path_count DESC
        LIMIT $limit
        """
        
        results = await self.db.execute_read(query, {
            "entry_ids": entry_ids,
            "limit": limit
        })
        
        formatted = []
        for record in results:
            entry_data = record.get('e2', {})
            formatted.append({
                "id": entry_data.get('id'),
                "title": entry_data.get('title'),
                "description": entry_data.get('description'),
                "graph_score": record.get('path_count', 0),
                "relationship_types": record.get('relationship_types', []),
                "source": "graph_related"
            })
        
        return formatted
