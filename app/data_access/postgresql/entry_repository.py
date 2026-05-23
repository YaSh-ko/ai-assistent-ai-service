from typing import Optional, Dict, Any, List
from datetime import date
from uuid import UUID
from app.data_access.postgresql.base_repository import BasePostgreSQLRepository
from app.interfaces.repositories.i_entry_repository import IEntryRepository

class EntryRepository(BasePostgreSQLRepository, IEntryRepository):
    """Repository for managing entries."""

    async def create(self, user_id: str, title: str, description: str, event_date: date) -> Optional[Dict[str, Any]]:
        """Create a new entry."""
        query = """
            INSERT INTO entries (user_id, title, description, event_date)
            VALUES ($1, $2, $3, $4)
            RETURNING *
        """
        return await self.fetch_one(query, user_id, title, description, event_date)

    async def get_by_id(self, id: UUID) -> Optional[Dict[str, Any]]:
        """Get entry by ID."""
        query = "SELECT * FROM entries WHERE id = $1"
        return await self.fetch_one(query, id)

    async def get_by_ids(self, ids: List[UUID]) -> List[Dict[str, Any]]:
        """Get entries by a list of IDs."""
        if not ids:
            return []
        query = "SELECT * FROM entries WHERE id = ANY($1::uuid[])"
        return await self.fetch_all(query, ids)

    async def update(self, id: UUID, description: Optional[str] = None, title: Optional[str] = None, event_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        """Update an entry."""
        # Build dynamic query
        set_clauses = []
        values = []
        idx = 1
        
        if description is not None:
            set_clauses.append(f"description = ${idx}")
            values.append(description)
            idx += 1
        
        if title is not None:
            set_clauses.append(f"title = ${idx}")
            values.append(title)
            idx += 1
            
        if event_date is not None:
            set_clauses.append(f"event_date = ${idx}")
            values.append(event_date)
            idx += 1
            
        if not set_clauses:
            return await self.get_by_id(id)
            
        values.append(id)
        query = f"""
            UPDATE entries
            SET {', '.join(set_clauses)}
            WHERE id = ${idx}
            RETURNING *
        """
        return await self.fetch_one(query, *values)

    async def delete(self, id: UUID) -> bool:
        """Delete an entry."""
        query = "DELETE FROM entries WHERE id = $1"
        result = await self.execute(query, id)
        return "DELETE 0" not in result

    async def count_by_user(self, user_id: str) -> int:
        """Count entries by user."""
        query = "SELECT COUNT(*) FROM entries WHERE user_id = $1"
        result = await self.fetch_one(query, user_id)
        return result['count'] if result else 0
