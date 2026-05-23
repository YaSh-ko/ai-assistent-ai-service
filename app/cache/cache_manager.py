from app.factory.cache_factory import CacheFactory
from app.core.config import settings

class CacheManager:
    """Manager for caching."""
    
    def __init__(self):
        self.provider = CacheFactory.create_cache_provider(settings.SESSION_CONFIG["cache_provider"])

    async def get(self, key: str):
        return await self.provider.get(key)

    async def set(self, key: str, value: Any, ttl: int = None):
        await self.provider.set(key, value, ttl)
