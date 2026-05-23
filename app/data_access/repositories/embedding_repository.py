from typing import Any, Dict, List, Optional
from app.data_access.repositories.base_repository import BaseRepository
from app.interfaces.vector_store import IVectorStore

class EmbeddingRepository(BaseRepository):
    """Repository for vector data."""
    
    def __init__(self, vector_store: IVectorStore):
        self._vector_store = vector_store

    async def search_similar(self, embedding: List[float], k: int = 5, filter: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        return await self._vector_store.similarity_search(query_embedding=embedding, k=k, filter=filter)

    async def add_embedding(self, document_id: str, embedding: List[float], metadata: Dict[str, Any], page_content: str) -> None:
        # The interface add_documents expects a list of dicts and list of embeddings
        document = {
            "id": document_id,
            "page_content": page_content,
            "metadata": metadata
        }
        await self._vector_store.add_documents([document], [embedding])
        
    async def add_embeddings(self, documents: List[Dict[str, Any]], embeddings: List[List[float]]) -> None:
        """Batch add embeddings."""
        await self._vector_store.add_documents(documents, embeddings)

    async def reset(self) -> None:
        """Reset the repository data."""
        await self._vector_store.reset()

    async def delete_embedding(self, document_id: str) -> None:
        """Delete embedding by ID."""
        await self._vector_store.delete_documents([document_id])

    async def delete_embeddings(self, document_ids: List[str]) -> None:
        """Batch delete embeddings."""
        await self._vector_store.delete_documents(document_ids)

    async def update_embedding(self, document_id: str, new_embedding: List[float], new_metadata: Dict[str, Any], new_page_content: str) -> None:
        """Update embedding by deleting and re-adding."""
        # Since Chroma doesn't support direct update of everything easily in one go via common interface,
        # we delete and re-add.
        await self.delete_embedding(document_id)
        await self.add_embedding(document_id, new_embedding, new_metadata, new_page_content)

    async def get_by_metadata(self, filter: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get documents by metadata filter."""
        return await self._vector_store.get_by_filter(filter)

    async def get_by_entry_id(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Get document by entry_id (stored in metadata)."""
        results = await self.get_by_metadata({"entry_id": entry_id})
        return results[0] if results else None

    async def search_by_user(self, user_id: str, query_embedding: List[float], k: int = 5) -> List[Dict[str, Any]]:
        """Search similar documents for a specific user."""
        return await self.search_similar(embedding=query_embedding, k=k, filter={"user_id": user_id})

    async def count_by_user(self, user_id: str) -> int:
        """Count documents for a specific user."""
        results = await self.get_by_metadata({"user_id": user_id})
        return len(results)
