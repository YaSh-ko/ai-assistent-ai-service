import re
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.data_access.postgresql.base_repository import BasePostgreSQLRepository
from app.models.chat_session import ChatSession, SessionStatus

class ChatSessionRepository(BasePostgreSQLRepository):
    """Repository for managing chat sessions."""

    def _parse_json_fields(self, row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Parse JSON strings back to dictionaries/lists."""
        if not row:
            return None
        
        import json
        json_fields = ['history', 'context', 'metadata', 'states']
        for field in json_fields:
            if field in row and isinstance(row[field], str):
                try:
                    row[field] = json.loads(row[field])
                except Exception:
                    # Fallback if it's already a dict or invalid JSON
                    pass
        return row

    async def create(self, user_id: str, thread_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Create a new chat session (now using conversations table)."""
        if not thread_id:
            raise ValueError("thread_id is required")
        query = """
            INSERT INTO conversations (thread_id, user_id, history, context, metadata, states, created_at, last_active_at)
            VALUES ($1, $2, '[]'::jsonb, '{}'::jsonb, '{}'::jsonb, '[]'::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (thread_id) DO UPDATE SET last_active_at = CURRENT_TIMESTAMP
            RETURNING *
        """
        row = await self.fetch_one(query, thread_id, user_id)
        return self._parse_json_fields(row)

    async def get_by_id(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get session by thread_id (from conversations table)."""
        query = "SELECT * FROM conversations WHERE thread_id = $1"
        row = await self.fetch_one(query, thread_id)
        return self._parse_json_fields(row)

    async def update(self, thread_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update session data."""
        import json
        from datetime import datetime
        
        def json_encoder(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return str(obj)

        # Construct dynamic update query
        set_clauses = []
        values = []
        idx = 1
        
        for key, value in data.items():
            if key in ['context', 'metadata', 'history', 'states']:
                # Manual serialization for jsonb
                value = json.dumps(value, default=json_encoder)
                set_clauses.append(f"{key} = ${idx}::jsonb")
            else:
                set_clauses.append(f"{key} = ${idx}")
            values.append(value)
            idx += 1
            
        # Always update last_active_at
        set_clauses.append("last_active_at = CURRENT_TIMESTAMP")
        
        query = f"""
            UPDATE conversations
            SET {', '.join(set_clauses)}
            WHERE thread_id = ${idx}
            RETURNING *
        """
        values.append(thread_id)
        
        row = await self.fetch_one(query, *values)
        return self._parse_json_fields(row)

    async def delete(self, thread_id: str) -> bool:
        """Delete a conversation."""
        query = "DELETE FROM conversations WHERE thread_id = $1"
        result = await self.execute(query, thread_id)
        return "DELETE 0" not in result

    async def add_message(self, thread_id: str, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add a message to the session history."""
        import json
        from datetime import datetime

        def json_encoder(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return str(obj)
        
        message_array_json = json.dumps([message], default=json_encoder)
        query = """
            UPDATE conversations
            SET history = history || $1::jsonb,
                last_active_at = CURRENT_TIMESTAMP
            WHERE thread_id = $2
            RETURNING *
        """
        row = await self.fetch_one(query, message_array_json, thread_id)
        return self._parse_json_fields(row)

    async def get_history(self, thread_id: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """Get session history with pagination."""
        query = "SELECT history FROM conversations WHERE thread_id = $1"
        row = await self.fetch_one(query, thread_id)
        row = self._parse_json_fields(row)
        if not row or not row.get('history'):
            return []
            
        history = row['history']
        # Apply offset and limit
        end = len(history) - offset
        start = max(0, end - limit)
        return history[start:end] if end > 0 else []

    async def cleanup_closed(self, retention_hours: int = 24) -> int:
        """Delete conversations marked closed in metadata and inactive beyond retention."""
        query = """
            DELETE FROM conversations
            WHERE COALESCE(metadata->>'status', '') = 'closed'
              AND last_active_at < CURRENT_TIMESTAMP - ($1::bigint * interval '1 hour')
        """
        result = await self.execute(query, retention_hours)
        if not result:
            return 0
        m = re.match(r"DELETE (\d+)", result)
        return int(m.group(1)) if m else 0
