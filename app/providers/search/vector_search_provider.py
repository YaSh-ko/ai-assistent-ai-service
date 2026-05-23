from typing import List, Dict, Any
from app.interfaces.vector_store import IVectorStore

class VectorSearchProvider:
    """
    Provider for vector-based semantic search.
    Uses ChromaDB (or any IVectorStore implementation) to perform similarity search.
    """
    def __init__(self, vector_store: IVectorStore):
        """
        Initialize the vector search provider.
        
        Args:
            vector_store: The vector store implementation (e.g., ChromaProvider)
        """
        self._vector_store = vector_store

    async def search(self, query_embedding: List[float], top_k: int = 5, **kwargs) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search.
        
        Args:
            query_embedding: The embedding vector of the query
            top_k: Number of top results to return
            **kwargs: Additional arguments like 'filter' for metadata filtering
            
        Returns:
            List of dictionaries containing:
                - page_content: The document text
                - metadata: Document metadata (e.g., user_id, entry_id, timestamp)
                - score: Similarity score
        """
        filter_criteria = kwargs.get('filter')
        
        results = await self._vector_store.similarity_search(
            query_embedding=query_embedding,
            k=top_k,
            filter=filter_criteria
        )
        
        return results
