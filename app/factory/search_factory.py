from typing import Optional
from app.interfaces.search_provider import ISearchProvider
from app.interfaces.reranker import IReranker
from app.interfaces.relational_database import IRelationalDatabase
from app.interfaces.vector_store import IVectorStore
from app.providers.search.bm25_provider import BM25Provider
from app.providers.search.vector_search_provider import VectorSearchProvider
from app.providers.search.hybrid_search_provider import HybridSearchProvider
from app.providers.search.reranker_provider import RerankerProvider
from app.core.config import settings


class SearchFactory:
    """Factory for creating search provider instances with proper dependency injection."""
    
    @staticmethod
    def create_bm25_provider(postgres_pool) -> BM25Provider:
        """
        Create a BM25 search provider.
        
        Args:
            postgres_pool: PostgreSQL connection pool (from PostgresProvider.pool)
            
        Returns:
            BM25Provider instance
        """
        return BM25Provider(postgres_pool)
    
    @staticmethod
    def create_vector_provider(vector_store: IVectorStore) -> VectorSearchProvider:
        """
        Create a vector search provider.
        
        Args:
            vector_store: Vector store instance (e.g., ChromaProvider)
            
        Returns:
            VectorSearchProvider instance
        """
        return VectorSearchProvider(vector_store)
    
    @staticmethod
    def create_hybrid_provider(
        postgres_pool,
        vector_store: IVectorStore
    ) -> HybridSearchProvider:
        """
        Create a hybrid search provider.
        
        Args:
            postgres_pool: PostgreSQL connection pool
            vector_store: Vector store instance
            
        Returns:
            HybridSearchProvider instance
        """
        bm25 = SearchFactory.create_bm25_provider(postgres_pool)
        vector = SearchFactory.create_vector_provider(vector_store)
        return HybridSearchProvider(bm25, vector)
    
    @staticmethod
    def create_search_provider(
        search_type: Optional[str] = None,
        postgres_pool = None,
        vector_store: Optional[IVectorStore] = None
    ) -> ISearchProvider:
        """
        Create a search provider based on type.
        
        Args:
            search_type: Type of search provider ("bm25", "vector", "hybrid")
                        If None, uses SEARCH_TYPE from config
            postgres_pool: PostgreSQL connection pool (required for bm25 and hybrid)
            vector_store: Vector store instance (required for vector and hybrid)
            
        Returns:
            ISearchProvider instance
            
        Raises:
            ValueError: If search type is unknown or required dependencies are missing
        """
        if search_type is None:
            search_type = settings.SEARCH_CONFIG.get("search_type", "hybrid")
        
        search_type = search_type.lower()
        
        if search_type == "bm25":
            if postgres_pool is None:
                raise ValueError("postgres_pool is required for BM25 search provider")
            return SearchFactory.create_bm25_provider(postgres_pool)
        
        elif search_type == "vector":
            if vector_store is None:
                raise ValueError("vector_store is required for vector search provider")
            return SearchFactory.create_vector_provider(vector_store)
        
        elif search_type == "hybrid":
            if postgres_pool is None or vector_store is None:
                raise ValueError("Both postgres_pool and vector_store are required for hybrid search provider")
            return SearchFactory.create_hybrid_provider(postgres_pool, vector_store)
        
        else:
            raise ValueError(f"Unknown search provider type: {search_type}. Must be 'bm25', 'vector', or 'hybrid'")
    
    @staticmethod
    def create_reranker(provider_type: str = "default") -> IReranker:
        """
        Create a reranker instance.
        
        Args:
            provider_type: Type of reranker (default: "default")
            
        Returns:
            IReranker instance
        """
        # Assuming default is our RerankerProvider for now
        return RerankerProvider()
