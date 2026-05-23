import asyncio
import random
from typing import Any, Dict, List
from app.services.chunking_service import ChunkingService
from app.interfaces.embeddings_provider import IEmbeddingsProvider
from app.data_access.repositories.embedding_repository import EmbeddingRepository

import logging
logger = logging.getLogger(__name__)

_RETRY_DELAYS = [1.0, 2.0, 4.0, 8.0]  # секунды между попытками при 429
_SYSTEM_RANDOM = random.SystemRandom()


def _get_retry_delay(base_delay: float) -> float:
    """Добавляет jitter к задержке для избежания thundering herd."""
    return base_delay * (0.5 + _SYSTEM_RANDOM.random())


async def _with_retry(coro_fn, *args, **kwargs):
    """Вызывает coro_fn с retry при 429 (exponential backoff с jitter)."""
    last_exc = None
    for attempt in range(len(_RETRY_DELAYS) + 1):
        if attempt > 0:
            delay = _get_retry_delay(_RETRY_DELAYS[attempt - 1])
            logger.warning(
                f"429 от GigaChat, попытка {attempt + 1}/{len(_RETRY_DELAYS) + 1}, "
                f"жду {delay:.2f}с"
            )
            await asyncio.sleep(delay)
        try:
            return await coro_fn(*args, **kwargs)
        except Exception as e:
            msg = str(e)
            if "429" in msg or "Too Many Requests" in msg.lower():
                last_exc = e
                continue
            raise
    if last_exc:
        raise last_exc

class EmbeddingService:
    def __init__(
        self, 
        chunking_service: ChunkingService,
        embeddings_provider: IEmbeddingsProvider,
        embedding_repository: EmbeddingRepository
    ):
        self._chunking_service = chunking_service
        self._embeddings_provider = embeddings_provider
        self._embedding_repository = embedding_repository

    async def process_text(self, text: str, metadata: Dict[str, Any]) -> None:
        # 1. Chunking
        # Check if it's a chat log based on metadata or content, for now we assume if it has "User:" it might be chat
        # But better to have a flag or just use split_chat_history if it looks like chat.
        # For this task, we'll assume we want to use split_chat_history if it's available, or just use it.
        # The task specifically mentions "splitting and chunking the chat_history".
        
        chunks = self._chunking_service.split_chat_history(text)
        
        if not chunks:
            return

        # 2. Embedding
        try:
            # No instruction for documents
            embeddings = await self._embeddings_provider.embed_documents(chunks)
        except Exception as e:
            print(f"Error generating embeddings: {repr(e)}")
            import traceback
            traceback.print_exc()
            raise e
        
        # 3. Prepare documents for repository
        documents = []
        for i, chunk in enumerate(chunks):
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_index"] = i
            # We might want to generate a unique ID for each chunk or let the DB handle it.
            # For now, we'll let the DB handle IDs or pass None.
            documents.append({
                "page_content": chunk,
                "metadata": chunk_metadata
            })
            
        # 4. Save to repository
        try:
            await self._embedding_repository.add_embeddings(documents, embeddings)
        except Exception as e:
            print(f"Error saving embeddings to repository: {e}")
            raise e

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text string, с retry при 429."""
        async def _do():
            if hasattr(self._embeddings_provider, "embed_query"):
                return await self._embeddings_provider.embed_query(text)
            embeddings = await self._embeddings_provider.embed_documents([text])
            return embeddings[0]

        try:
            return await _with_retry(_do)
        except Exception as e:
            print(f"Error generating embedding: {e}")
            raise e
