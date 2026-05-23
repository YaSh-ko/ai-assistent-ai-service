"""
Tests for CacheFactory and CacheManager.
"""
import pytest
from unittest.mock import patch, MagicMock

from app.factory.cache_factory import CacheFactory
from app.providers.cache.memory_provider import MemoryProvider
from app.providers.cache.redis_provider import RedisProvider


class TestCacheFactory:
    def test_creates_memory_provider(self):
        provider = CacheFactory.create_cache_provider("memory")
        assert isinstance(provider, MemoryProvider)

    def test_creates_redis_provider(self):
        provider = CacheFactory.create_cache_provider("redis")
        assert isinstance(provider, RedisProvider)

    def test_raises_on_unknown_type(self):
        with pytest.raises(ValueError, match="Unknown cache provider type"):
            CacheFactory.create_cache_provider("unknown")

    def test_raises_on_empty_string(self):
        with pytest.raises(ValueError):
            CacheFactory.create_cache_provider("")


class TestMemoryProvider:
    @pytest.mark.asyncio
    async def test_get_returns_none(self):
        p = MemoryProvider()
        result = await p.get("key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_does_not_raise(self):
        p = MemoryProvider()
        await p.set("key", "value", ttl=60)

    @pytest.mark.asyncio
    async def test_delete_does_not_raise(self):
        p = MemoryProvider()
        await p.delete("key")


class TestRedisProvider:
    @pytest.mark.asyncio
    async def test_get_returns_none(self):
        p = RedisProvider()
        result = await p.get("key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_does_not_raise(self):
        p = RedisProvider()
        await p.set("key", "value")

    @pytest.mark.asyncio
    async def test_delete_does_not_raise(self):
        p = RedisProvider()
        await p.delete("key")
