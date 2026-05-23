from abc import ABC, abstractmethod
from typing import Any, Dict, List

class IReranker(ABC):
    """Interface for rerankers."""

    @abstractmethod
    async def rerank(self, query: str, documents: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
        """Rerank a list of documents based on the query."""
        pass
