"""
Tests for EmbeddingService — 31 uncovered lines.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.embedding_service import EmbeddingService


@pytest.fixture
def mock_chunking_service():
    svc = MagicMock()
    svc.split_chat_history = MagicMock(return_value=["chunk one", "chunk two"])
    return svc


@pytest.fixture
def mock_embeddings_provider():
    p = MagicMock()
    p.embed_documents = AsyncMock(return_value=[[0.1] * 1024, [0.2] * 1024])
    p.embed_query = AsyncMock(return_value=[0.3] * 1024)
    return p


@pytest.fixture
def mock_embedding_repository():
    r = MagicMock()
    r.add_embeddings = AsyncMock(return_value=None)
    r.search_similar = AsyncMock(return_value=[])
    return r


@pytest.fixture
def service(mock_chunking_service, mock_embeddings_provider, mock_embedding_repository):
    return EmbeddingService(
        chunking_service=mock_chunking_service,
        embeddings_provider=mock_embeddings_provider,
        embedding_repository=mock_embedding_repository,
    )


class TestProcessText:
    @pytest.mark.asyncio
    async def test_process_text_full_pipeline(self, service, mock_chunking_service,
                                               mock_embeddings_provider, mock_embedding_repository):
        await service.process_text("some diary text", {"user_id": "u1"})

        mock_chunking_service.split_chat_history.assert_called_once_with("some diary text")
        mock_embeddings_provider.embed_documents.assert_called_once_with(["chunk one", "chunk two"])
        mock_embedding_repository.add_embeddings.assert_called_once()

        docs, embeddings = mock_embedding_repository.add_embeddings.call_args[0]
        assert len(docs) == 2
        assert docs[0]["page_content"] == "chunk one"
        assert docs[0]["metadata"]["chunk_index"] == 0
        assert docs[1]["metadata"]["chunk_index"] == 1

    @pytest.mark.asyncio
    async def test_process_text_empty_chunks_returns_early(self, service, mock_chunking_service,
                                                            mock_embedding_repository):
        mock_chunking_service.split_chat_history = MagicMock(return_value=[])
        await service.process_text("", {"user_id": "u1"})
        mock_embedding_repository.add_embeddings.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_text_embed_error_propagates(self, service, mock_embeddings_provider):
        mock_embeddings_provider.embed_documents = AsyncMock(side_effect=RuntimeError("embed fail"))
        with pytest.raises(RuntimeError, match="embed fail"):
            await service.process_text("text", {"user_id": "u1"})

    @pytest.mark.asyncio
    async def test_process_text_save_error_propagates(self, service, mock_embedding_repository):
        mock_embedding_repository.add_embeddings = AsyncMock(side_effect=RuntimeError("save fail"))
        with pytest.raises(RuntimeError, match="save fail"):
            await service.process_text("text", {"user_id": "u1"})

    @pytest.mark.asyncio
    async def test_metadata_preserved_per_chunk(self, service, mock_embedding_repository):
        await service.process_text("text", {"user_id": "u1", "entry_id": "e1"})
        docs, _ = mock_embedding_repository.add_embeddings.call_args[0]
        for doc in docs:
            assert doc["metadata"]["user_id"] == "u1"
            assert doc["metadata"]["entry_id"] == "e1"


class TestGenerateEmbedding:
    @pytest.mark.asyncio
    async def test_uses_embed_query_when_available(self, service, mock_embeddings_provider):
        result = await service.generate_embedding("hello")
        mock_embeddings_provider.embed_query.assert_called_once_with("hello")
        assert result == [0.3] * 1024

    @pytest.mark.asyncio
    async def test_falls_back_to_embed_documents(self, service, mock_embeddings_provider):
        del mock_embeddings_provider.embed_query
        mock_embeddings_provider.embed_documents = AsyncMock(return_value=[[0.5] * 1024])
        result = await service.generate_embedding("hello")
        assert result == [0.5] * 1024

    @pytest.mark.asyncio
    async def test_generate_embedding_error_propagates(self, service, mock_embeddings_provider):
        mock_embeddings_provider.embed_query = AsyncMock(side_effect=ValueError("bad"))
        with pytest.raises(ValueError, match="bad"):
            await service.generate_embedding("hello")
