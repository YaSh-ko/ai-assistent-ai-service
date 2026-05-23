from typing import Dict, List, Any
from app.data_access.neo4j.relationships.base_relationship_repository import BaseRelationshipRepository

class RelationshipQueryRepository(BaseRelationshipRepository):
    """
    Repository for complex relationship queries and analytics.
    """

    async def find_all_connections(
        self,
        node_id: str,
        depth: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Find all connected nodes up to a certain depth.
        """
        query = f"""
        MATCH path = (n {{id: $node_id}})-[*1..{depth}]-(connected)
        RETURN connected, relationships(path) as rels, length(path) as distance
        ORDER BY distance ASC
        LIMIT 100
        """
        return await self._execute_read(query, {"node_id": node_id})

    async def get_relationship_summary(self, user_id: str) -> Dict[str, int]:
        """
        Get a summary of relationship counts for a user's graph.
        """
        query = """
        MATCH (n {user_id: $user_id})-[r]-()
        RETURN type(r) as rel_type, count(r) as count
        ORDER BY count DESC
        """
        result = await self._execute_read(query, {"user_id": user_id})
        
        summary = {}
        for record in result:
            summary[record["rel_type"]] = record["count"]
        
        return summary

    async def find_path_between_nodes(
        self,
        from_id: str,
        to_id: str,
        max_depth: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find the shortest path between two nodes.
        """
        query = f"""
        MATCH path = shortestPath((from {{id: $from_id}})-[*1..{max_depth}]-(to {{id: $to_id}}))
        RETURN nodes(path) as nodes, relationships(path) as rels, length(path) as length
        """
        return await self._execute_read(query, {"from_id": from_id, "to_id": to_id})

    async def get_most_connected_nodes(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most connected nodes in a user's graph.
        """
        query = """
        MATCH (n {user_id: $user_id})-[r]-()
        WITH n, count(r) as connection_count
        RETURN n, connection_count
        ORDER BY connection_count DESC
        LIMIT $limit
        """
        return await self._execute_read(query, {"user_id": user_id, "limit": limit})

    async def get_concept_network(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get the concept evolution network for a user.
        """
        query = """
        MATCH (c1:Concept {user_id: $user_id})-[r:EVOLVES_INTO]->(c2:Concept)
        RETURN c1, r, c2
        ORDER BY r.evolved_at DESC
        """
        return await self._execute_read(query, {"user_id": user_id})

    async def get_goal_progress_overview(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get an overview of goal progress based on entry connections.
        """
        query = """
        MATCH (g:Goal {user_id: $user_id})<-[r:RELATES_TO]-(e:Entry)
        WITH g, r.relation_type as relation_type, count(e) as entry_count
        RETURN g, collect({type: relation_type, count: entry_count}) as progress_data
        ORDER BY g.created_at DESC
        """
        return await self._execute_read(query, {"user_id": user_id})
