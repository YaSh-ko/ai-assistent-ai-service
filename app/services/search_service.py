from typing import Any, Dict, List, Optional
from app.interfaces.embeddings_provider import IEmbeddingsProvider
from app.data_access.repositories.embedding_repository import EmbeddingRepository
from app.core.config import settings

class SearchService:
    def __init__(
        self,
        embeddings_provider: IEmbeddingsProvider,
        embedding_repository: EmbeddingRepository
    ):
        self._embeddings_provider = embeddings_provider
        self._embedding_repository = embedding_repository

    async def search(self, query: str, k: int = settings.CHUNKING_CONFIG["top_k_results"], filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        # 1. Embed query with instruction
        instruction = "Дан вопрос, необходимо найти абзац текста с ответом. Вопрос:"
        # Note: The instruction format in the guide was: "Дан вопрос, необходимо найти абзац текста с ответом. Вопрос: {query}"
        # But the provider logic I implemented prepends the instruction to the text.
        # So here I should pass the instruction prefix.
        # Wait, my provider implementation was: text = f"{instruction} {text}"
        # So if I pass instruction="...", it becomes "... query".
        # The guide said: "Дан вопрос... Вопрос: {query}"
        # So the instruction string should be "Дан вопрос, необходимо найти абзац текста с ответом. Вопрос:"
        
        query_embedding = await self._embeddings_provider.embed_query(query, instruction=instruction)
        
        # 2. Search in repository
        results = await self._embedding_repository.search_similar(embedding=query_embedding, k=k, filter=filter)
        
        return results
