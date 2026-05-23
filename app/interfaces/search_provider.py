from abc import ABC, abstractmethod
from typing import Any, Dict, List

class ISearchProvider(ABC):
    """Interface for search providers."""

    @abstractmethod
    async def search(self, query: str, k: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """Perform a search query."""
        pass
