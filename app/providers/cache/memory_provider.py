from typing import Any, Dict, Optional, Tuple
import time
from app.interfaces.cache_provider import ICacheProvider


class MemoryProvider(ICacheProvider):
    """In-memory cache provider with optional TTL support."""

    def __init__(self):
        # Stores (value, expiry_timestamp_or_None)
        self._store: Dict[str, Tuple[Any, Optional[float]]] = {}

    async def get(self, key: str) -> Optional[Any]:
        """Return cached value, or None if missing/expired."""
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if expiry is not None and time.time() > expiry:
            del self._store[key]
            return None
        return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store a value with an optional TTL in seconds."""
        expiry = time.time() + ttl if ttl is not None else None
        self._store[key] = (value, expiry)

    async def delete(self, key: str) -> None:
        """Remove a key from the cache."""
        self._store.pop(key, None)
