import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

from app.interfaces.cache_provider import ICacheProvider
from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisProvider(ICacheProvider):
    """Redis-backed cache provider using redis.asyncio."""

    def __init__(self, url: Optional[str] = None):
        self._url = url or settings.REDIS_URL
        self._client: Optional[aioredis.Redis] = None

    def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(self._url, decode_responses=True)
        return self._client

    async def get(self, key: str) -> Optional[Any]:
        """Return deserialized value for key, or None if missing."""
        try:
            raw = await self._get_client().get(key)
            return json.loads(raw) if raw is not None else None
        except Exception as e:
            logger.error(f"Redis GET error for key '{key}': {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Serialize and store value, with optional TTL in seconds."""
        try:
            serialized = json.dumps(value)
            if ttl is not None:
                await self._get_client().setex(key, ttl, serialized)
            else:
                await self._get_client().set(key, serialized)
        except Exception as e:
            logger.error(f"Redis SET error for key '{key}': {e}")

    async def delete(self, key: str) -> None:
        """Remove a key from Redis."""
        try:
            await self._get_client().delete(key)
        except Exception as e:
            logger.error(f"Redis DELETE error for key '{key}': {e}")
