from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class IVectorStore(ABC):
    """Interface for vector stores."""

    @abstractmethod
    async def add_documents(self, documents: List[Dict[str, Any]], embeddings: List[List[float]]) -> None:
        """Add documents and their embeddings to the store."""
        pass

    @abstractmethod
    async def similarity_search(
        self, 
        query_embedding: List[float], 
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar documents."""
        pass

    @abstractmethod
    async def reset(self) -> None:
        """Reset/Clear the vector store."""
        pass

    @abstractmethod
    async def delete_documents(self, ids: List[str]) -> None:
        """Delete documents by IDs."""
        pass

    @abstractmethod
    async def get_by_filter(self, filter: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get documents by metadata filter."""
        pass
