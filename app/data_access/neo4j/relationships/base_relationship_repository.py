from typing import Dict, List, Optional, Any
from app.data_access.repositories.base_repository import BaseGraphRepository

class BaseRelationshipRepository(BaseGraphRepository):
    """
    Base class for all relationship repositories.
    """

    async def get_relationships(
        self,
        node_id: str,
        rel_type: Optional[str] = None,
        direction: str = "OUTGOING"
    ) -> List[Dict[str, Any]]:
        """
        Get all relationships for a node.
        
        Args:
            node_id: ID of the node
            rel_type: Optional relationship type to filter by
            direction: "OUTGOING", "INCOMING", or "BOTH"
        """
        if direction == "OUTGOING":
            pattern = "(n)-[r]->()"
        elif direction == "INCOMING":
            pattern = "()<-[r]-(n)"
        else:  # BOTH
            pattern = "(n)-[r]-()"
        
        where_clauses = ["n.id = $node_id"]
        params = {"node_id": node_id}
        
        if rel_type:
            where_clauses.append("type(r) = $rel_type")
            params["rel_type"] = rel_type
        
        where_query = " AND ".join(where_clauses)
        
        query = f"""
        MATCH {pattern}
        WHERE {where_query}
        RETURN r, type(r) as rel_type, id(r) as rel_id
        """
        
        result = await self._execute_read(query, params)
        return result

    async def delete_relationship(self, rel_id: int) -> bool:
        """
        Delete a relationship by its internal Neo4j ID.
        """
        query = """
        MATCH ()-[r]->()
        WHERE id(r) = $rel_id
        DELETE r
        """
        result = await self._execute_write(query, {"rel_id": rel_id})
        return result.get("relationships_deleted", 0) > 0

    async def _create_relationship(
        self,
        from_id: str,
        to_id: str,
        from_label: str,
        to_label: str,
        rel_type: str,
        properties: Dict[str, Any]
    ) -> str:
        """
        Generic method to create a relationship between two nodes.
        
        Args:
            from_id: ID of the source node
            to_id: ID of the target node
            from_label: Label of the source node (e.g., "Entry")
            to_label: Label of the target node (e.g., "Concept")
            rel_type: Type of relationship (e.g., "MENTIONS")
            properties: Properties for the relationship
        """
        # Build properties string
        props_list = []
        params = {
            "from_id": from_id,
            "to_id": to_id
        }
        
        for key, value in properties.items():
            props_list.append(f"{key}: ${key}")
            params[key] = value
        
        props_string = ", ".join(props_list) if props_list else ""
        props_part = f" {{{props_string}}}" if props_string else ""
        
        query = f"""
        MATCH (from:{from_label} {{id: $from_id}}), (to:{to_label} {{id: $to_id}})
        CREATE (from)-[r:{rel_type}{props_part}]->(to)
        RETURN id(r) as rel_id
        """

        await self._execute_write(query, params)
        return f"{from_id}_{rel_type}_{to_id}"

    async def _find_by_relationship(
        self,
        target_id: str,
        target_label: str,
        rel_type: str,
        source_label: str,
        user_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find source nodes connected to a target node via a specific relationship.
        
        Args:
            target_id: ID of the target node
            target_label: Label of the target node
            rel_type: Relationship type
            source_label: Label of the source nodes to return
            user_id: User ID for filtering
            limit: Maximum results
        """
        query = f"""
        MATCH (s:{source_label})-[r:{rel_type}]->(t:{target_label} {{id: $target_id}})
        WHERE s.user_id = $user_id
        RETURN s, r
        ORDER BY s.created_at DESC
        LIMIT $limit
        """
        
        result = await self._execute_read(query, {
            "target_id": target_id,
            "user_id": user_id,
            "limit": limit
        })
        
        return result
