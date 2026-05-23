"""
Tests for SearchService.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.search_service import SearchService


@pytest.fixture
def mock_embeddings_provider():
    p = MagicMock()
    p.embed_query = AsyncMock(return_value=[0.1] * 1024)
    return p


@pytest.fixture
def mock_embedding_repository():
    r = MagicMock()
    r.search_similar = AsyncMock(return_value=[
        {"id": "1", "content": "Jupiter is the 5th planet"},
        {"id": "2", "content": "Saturn is the 6th planet"},
    ])
    return r


@pytest.fixture
def search_service(mock_embeddings_provider, mock_embedding_repository):
    return SearchService(
        embeddings_provider=mock_embeddings_provider,
        embedding_repository=mock_embedding_repository,
    )


class TestSearchService:
    @pytest.mark.asyncio
    async def test_search_returns_results(self, search_service, mock_embedding_repository):
        results = await search_service.search("5th planet")
        assert len(results) == 2
        assert results[0]["id"] == "1"

    @pytest.mark.asyncio
    async def test_search_embeds_query(self, search_service, mock_embeddings_provider):
        await search_service.search("5th planet")
        mock_embeddings_provider.embed_query.assert_called_once()
        call_kwargs = mock_embeddings_provider.embed_query.call_args
        assert "5th planet" in call_kwargs[0] or call_kwargs[1].get("query") == "5th planet" \
               or call_kwargs[0][0] == "5th planet"

    @pytest.mark.asyncio
    async def test_search_passes_filter(self, search_service, mock_embedding_repository):
        filt = {"user_id": "u1"}
        await search_service.search("query", filter=filt)
        call_kwargs = mock_embedding_repository.search_similar.call_args[1]
        assert call_kwargs.get("filter") == filt

    @pytest.mark.asyncio
    async def test_search_empty_results(self, search_service, mock_embedding_repository):
        mock_embedding_repository.search_similar = AsyncMock(return_value=[])
        results = await search_service.search("unknown")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_custom_k(self, search_service, mock_embedding_repository):
        await search_service.search("query", k=3)
        call_kwargs = mock_embedding_repository.search_similar.call_args[1]
        assert call_kwargs.get("k") == 3
