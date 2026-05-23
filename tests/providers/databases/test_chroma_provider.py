"""
Tests for ChromaProvider — 49 uncovered lines.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


def _make_provider():
    """Create a ChromaProvider with all external deps mocked."""
    mock_http_client = MagicMock()
    mock_chroma_client = MagicMock()

    with patch("chromadb.HttpClient", return_value=mock_http_client), \
         patch("app.providers.databases.chroma_provider.Chroma", return_value=mock_chroma_client), \
         patch("app.providers.databases.chroma_provider.settings") as mock_settings:

        mock_settings.CHROMA_SERVER_HOST = "localhost"
        mock_settings.CHROMA_SERVER_PORT = 8000
        mock_settings.CHROMA_SERVER_SSL = False
        mock_settings.SEARCH_CONFIG = {"distance_metric": "cosine"}

        from app.providers.databases.chroma_provider import ChromaProvider
        provider = ChromaProvider()
        provider._client = mock_chroma_client
        provider._http_client = mock_http_client

    return provider, mock_chroma_client


class TestAddDocuments:
    @pytest.mark.asyncio
    async def test_add_documents_calls_add_texts(self):
        provider, mock_client = _make_provider()
        docs = [
            {"page_content": "text1", "metadata": {"user_id": "u1"}, "id": "id1"},
            {"page_content": "text2", "metadata": {"user_id": "u1"}, "id": "id2"},
        ]
        embeddings = [[0.1] * 1024, [0.2] * 1024]

        await provider.add_documents(docs, embeddings)
        mock_client.add_texts.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_documents_none_ids_passed_as_none(self):
        provider, mock_client = _make_provider()
        docs = [{"page_content": "text", "metadata": {}}]
        embeddings = [[0.1] * 1024]

        await provider.add_documents(docs, embeddings)
        call_kwargs = mock_client.add_texts.call_args[1]
        assert call_kwargs.get("ids") is None

    @pytest.mark.asyncio
    async def test_add_documents_raises_on_error(self):
        provider, mock_client = _make_provider()
        mock_client.add_texts.side_effect = RuntimeError("chroma error")

        with pytest.raises(RuntimeError, match="chroma error"):
            await provider.add_documents([{"page_content": "t", "metadata": {}}], [[0.1]])


class TestSimilaritySearch:
    @pytest.mark.asyncio
    async def test_similarity_search_returns_results(self):
        provider, mock_client = _make_provider()
        from langchain_core.documents import Document
        mock_client.similarity_search_by_vector_with_relevance_scores.return_value = [
            (Document(page_content="Jupiter is big", metadata={"user_id": "u1"}), 0.95),
        ]

        results = await provider.similarity_search([0.1] * 1024, k=1)
        assert len(results) == 1
        assert results[0]["page_content"] == "Jupiter is big"
        assert results[0]["score"] == 0.95

    @pytest.mark.asyncio
    async def test_similarity_search_with_filter(self):
        provider, mock_client = _make_provider()
        mock_client.similarity_search_by_vector_with_relevance_scores.return_value = []

        await provider.similarity_search([0.1] * 1024, k=5, filter={"user_id": "u1"})
        call_kwargs = mock_client.similarity_search_by_vector_with_relevance_scores.call_args[1]
        assert call_kwargs["filter"] == {"user_id": "u1"}

    @pytest.mark.asyncio
    async def test_similarity_search_raises_on_error(self):
        provider, mock_client = _make_provider()
        mock_client.similarity_search_by_vector_with_relevance_scores.side_effect = RuntimeError("fail")

        with pytest.raises(RuntimeError):
            await provider.similarity_search([0.1] * 1024)


class TestReset:
    @pytest.mark.asyncio
    async def test_reset_deletes_and_recreates_collection(self):
        provider, mock_client = _make_provider()

        with patch("app.providers.databases.chroma_provider.Chroma") as mock_chroma_cls, \
             patch("app.providers.databases.chroma_provider.settings") as mock_settings:
            mock_settings.SEARCH_CONFIG = {"distance_metric": "cosine"}
            await provider.reset()

        mock_client.delete_collection.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_raises_on_error(self):
        provider, mock_client = _make_provider()
        mock_client.delete_collection.side_effect = RuntimeError("reset fail")

        with pytest.raises(RuntimeError, match="reset fail"):
            await provider.reset()


class TestDeleteDocuments:
    @pytest.mark.asyncio
    async def test_delete_documents_calls_delete(self):
        provider, mock_client = _make_provider()
        await provider.delete_documents(["id1", "id2"])
        mock_client.delete.assert_called_once_with(ids=["id1", "id2"])

    @pytest.mark.asyncio
    async def test_delete_documents_raises_on_error(self):
        provider, mock_client = _make_provider()
        mock_client.delete.side_effect = RuntimeError("delete fail")

        with pytest.raises(RuntimeError):
            await provider.delete_documents(["id1"])


class TestGetByFilter:
    @pytest.mark.asyncio
    async def test_get_by_filter_returns_documents(self):
        provider, mock_client = _make_provider()
        mock_client.get.return_value = {
            "ids": ["id1"],
            "documents": ["content1"],
            "metadatas": [{"user_id": "u1"}],
        }

        results = await provider.get_by_filter({"user_id": "u1"})
        assert len(results) == 1
        assert results[0]["id"] == "id1"
        assert results[0]["page_content"] == "content1"

    @pytest.mark.asyncio
    async def test_get_by_filter_empty_result(self):
        provider, mock_client = _make_provider()
        mock_client.get.return_value = {"ids": [], "documents": [], "metadatas": []}

        results = await provider.get_by_filter({"user_id": "u1"})
        assert results == []

    @pytest.mark.asyncio
    async def test_get_by_filter_raises_on_error(self):
        provider, mock_client = _make_provider()
        mock_client.get.side_effect = RuntimeError("filter fail")

        with pytest.raises(RuntimeError):
            await provider.get_by_filter({"user_id": "u1"})
