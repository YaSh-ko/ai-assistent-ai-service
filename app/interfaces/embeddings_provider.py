from abc import ABC, abstractmethod
from typing import List, Optional

class IEmbeddingsProvider(ABC):
    """Interface for embeddings providers."""

    @abstractmethod
    async def embed_query(self, text: str, instruction: Optional[str] = None) -> List[float]:
        """Embed a single query text."""
        pass

    @abstractmethod
    async def embed_documents(self, texts: List[str], instruction: Optional[str] = None) -> List[List[float]]:
        """Embed a list of documents."""
        pass
