from app.interfaces.cache_provider import ICacheProvider
from app.providers.cache.redis_provider import RedisProvider
from app.providers.cache.memory_provider import MemoryProvider

class CacheFactory:
    @staticmethod
    def create_cache_provider(provider_type: str) -> ICacheProvider:
        if provider_type == "redis":
            return RedisProvider()
        elif provider_type == "memory":
            return MemoryProvider()
        else:
            raise ValueError(f"Unknown cache provider type: {provider_type}")
