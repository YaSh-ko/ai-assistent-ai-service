from typing import Dict, List, Optional, Any
from datetime import datetime
from app.data_access.repositories.base_repository import BaseGraphRepository

class AnalysisRepository(BaseGraphRepository):
    """
    Repository for Analysis nodes.
    """

    async def create_analysis(
        self,
        analysis_id: str,
        title: str,
        user_id: str,
        content: str,
        summary: Optional[str] = None,
        analyzed_at: Optional[datetime] = None
    ) -> str:
        """
        Create a new Analysis node.
        """
        query = """
        CREATE (a:Analysis {
            id: $analysis_id,
            title: $title,
            user_id: $user_id,
            content: $content,
            summary: $summary,
            analyzed_at: datetime($analyzed_at),
            created_at: datetime(),
            updated_at: datetime()
        })
        RETURN a.id as id
        """
        params = {
            "analysis_id": analysis_id,
            "title": title,
            "user_id": user_id,
            "content": content,
            "summary": summary,
            "analyzed_at": self._format_datetime(analyzed_at)
        }
        await self._execute_write(query, params)
        return analysis_id

    async def get_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an Analysis by ID.
        """
        query = """
        MATCH (a:Analysis {id: $analysis_id})
        RETURN a
        """
        result = await self._execute_read(query, {"analysis_id": analysis_id})
        if result:
            return result[0]["a"]
        return None

    async def update_analysis(self, analysis_id: str, properties: Dict[str, Any]) -> bool:
        """
        Update an Analysis's properties.
        """
        set_clauses = []
        params = {"analysis_id": analysis_id}
        for key, value in properties.items():
            set_clauses.append(f"a.{key} = ${key}")
            params[key] = value
        
        if not set_clauses:
            return False

        set_clauses.append("a.updated_at = datetime()")
        set_query = ", ".join(set_clauses)

        query = f"""
        MATCH (a:Analysis {{id: $analysis_id}})
        SET {set_query}
        """
        result = await self._execute_write(query, params)
        return result.get("properties_set", 0) > 0

    async def delete_analysis(self, analysis_id: str) -> bool:
        """
        Delete an Analysis.
        """
        query = """
        MATCH (a:Analysis {id: $analysis_id})
        DETACH DELETE a
        """
        result = await self._execute_write(query, {"analysis_id": analysis_id})
        return result.get("nodes_deleted", 0) > 0

    async def find_by_user(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find analyses by user ID.
        """
        query = """
        MATCH (a:Analysis {user_id: $user_id})
        RETURN a
        ORDER BY a.analyzed_at DESC
        LIMIT $limit
        """
        result = await self._execute_read(query, {"user_id": user_id, "limit": limit})
        return [record["a"] for record in result]
