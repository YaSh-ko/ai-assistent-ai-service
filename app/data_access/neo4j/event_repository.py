from typing import Dict, List, Optional, Any
from datetime import datetime
from app.data_access.repositories.base_repository import BaseGraphRepository

class EventRepository(BaseGraphRepository):
    """
    Repository for Event nodes.
    """

    async def create_event(
        self,
        event_id: str,
        title: str,
        user_id: str,
        date: datetime,
        importance: float
    ) -> str:
        """
        Create a new Event node.
        """
        query = """
        CREATE (e:Event {
            id: $event_id,
            title: $title,
            user_id: $user_id,
            date: datetime($date),
            importance: $importance,
            created_at: datetime(),
            updated_at: datetime()
        })
        RETURN e.id as id
        """
        params = {
            "event_id": event_id,
            "title": title,
            "user_id": user_id,
            "date": self._format_datetime(date),
            "importance": importance
        }
        await self._execute_write(query, params)
        return event_id

    async def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an Event by ID.
        """
        query = """
        MATCH (e:Event {id: $event_id})
        RETURN e
        """
        result = await self._execute_read(query, {"event_id": event_id})
        if result:
            return result[0]["e"]
        return None

    async def update_event(self, event_id: str, properties: Dict[str, Any]) -> bool:
        """
        Update an Event's properties.
        """
        set_clauses = []
        params = {"event_id": event_id}
        for key, value in properties.items():
            set_clauses.append(f"e.{key} = ${key}")
            params[key] = value
        
        if not set_clauses:
            return False

        set_clauses.append("e.updated_at = datetime()")
        set_query = ", ".join(set_clauses)

        query = f"""
        MATCH (e:Event {{id: $event_id}})
        SET {set_query}
        """
        result = await self._execute_write(query, params)
        return result.get("properties_set", 0) > 0

    async def delete_event(self, event_id: str) -> bool:
        """
        Delete an Event.
        """
        query = """
        MATCH (e:Event {id: $event_id})
        DETACH DELETE e
        """
        result = await self._execute_write(query, {"event_id": event_id})
        return result.get("nodes_deleted", 0) > 0

    async def find_by_user(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find events by user ID.
        """
        query = """
        MATCH (e:Event {user_id: $user_id})
        RETURN e
        ORDER BY e.date DESC
        LIMIT $limit
        """
        result = await self._execute_read(query, {"user_id": user_id, "limit": limit})
        return [record["e"] for record in result]
