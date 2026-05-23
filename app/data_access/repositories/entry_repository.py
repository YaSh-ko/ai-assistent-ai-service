from typing import Dict, List, Optional, Any
from datetime import datetime
from app.data_access.repositories.base_repository import BaseGraphRepository

class EntryRepository(BaseGraphRepository):
    """
    Repository for Entry nodes.
    """

    async def create_entry(
        self,
        entry_id: str,
        user_id: str,
        session_id: str,
        timestamp: datetime,
        content: str,
        content_summary: Optional[str] = None,
        embedding_id: Optional[str] = None,
        word_count: Optional[int] = None,
        sentiment_score: float = 0.0
    ) -> str:
        """
        Create a new Entry node.
        """
        query = """
        CREATE (e:Entry {
            id: $entry_id,
            user_id: $user_id,
            session_id: $session_id,
            timestamp: datetime($timestamp),
            content: $content,
            content_summary: $content_summary,
            embedding_id: $embedding_id,
            word_count: $word_count,
            sentiment_score: $sentiment_score,
            created_at: datetime(),
            updated_at: datetime()
        })
        RETURN e.id as id
        """
        params = {
            "entry_id": entry_id,
            "user_id": user_id,
            "session_id": session_id,
            "timestamp": self._format_datetime(timestamp),
            "content": content,
            "content_summary": content_summary,
            "embedding_id": embedding_id,
            "word_count": word_count,
            "sentiment_score": sentiment_score
        }

        await self._execute_write(query, params)
        return entry_id

    async def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an Entry by ID.
        """
        query = """
        MATCH (e:Entry {id: $entry_id})
        RETURN e
        """
        result = await self._execute_read(query, {"entry_id": entry_id})
        if result:
            return result[0]["e"]
        return None

    async def update_entry(self, entry_id: str, properties: Dict[str, Any]) -> bool:
        """
        Update an Entry's properties.
        """
        # Construct SET clause dynamically
        set_clauses = []
        params = {"entry_id": entry_id}
        for key, value in properties.items():
            set_clauses.append(f"e.{key} = ${key}")
            params[key] = value
        
        if not set_clauses:
            return False

        set_clauses.append("e.updated_at = datetime()")
        set_query = ", ".join(set_clauses)

        query = f"""
        MATCH (e:Entry {{id: $entry_id}})
        SET {set_query}
        RETURN count(e) as count
        """
        
        result = await self._execute_write(query, params)
        
        return result.get("properties_set", 0) > 0

    async def delete_entry(self, entry_id: str) -> bool:
        """
        Delete an Entry.
        """
        query = """
        MATCH (e:Entry {id: $entry_id})
        DETACH DELETE e
        """
        result = await self._execute_write(query, {"entry_id": entry_id})
        return result.get("nodes_deleted", 0) > 0

    async def find_by_user(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find entries by user ID.
        """
        query = """
        MATCH (e:Entry {user_id: $user_id})
        RETURN e
        ORDER BY e.timestamp DESC
        LIMIT $limit
        """
        result = await self._execute_read(query, {"user_id": user_id, "limit": limit})
        return [record["e"] for record in result]
