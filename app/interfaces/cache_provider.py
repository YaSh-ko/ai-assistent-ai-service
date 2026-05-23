from abc import ABC, abstractmethod
from typing import Any, Optional

class ICacheProvider(ABC):
    """Interface for cache providers."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in the cache."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a value from the cache."""
        pass
