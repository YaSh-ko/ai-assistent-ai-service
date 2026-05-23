import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from app.factory.search_factory import SearchFactory
from app.providers.search.bm25_provider import BM25Provider
from app.providers.search.vector_search_provider import VectorSearchProvider
from app.providers.search.hybrid_search_provider import HybridSearchProvider


class TestSearchFactory:
    """Unit tests for SearchFactory methods."""
    
    def test_create_bm25_provider(self):
        """Test creation of BM25 provider with postgres pool."""
        # Arrange
        mock_pool = Mock()
        
        # Act
        provider = SearchFactory.create_bm25_provider(mock_pool)
        
        # Assert
        assert isinstance(provider, BM25Provider)
        assert provider.db_provider == mock_pool
    
    def test_create_vector_provider(self):
        """Test creation of vector search provider with vector store."""
        # Arrange
        mock_vector_store = Mock()
        
        # Act
        provider = SearchFactory.create_vector_provider(mock_vector_store)
        
        # Assert
        assert isinstance(provider, VectorSearchProvider)
        assert provider._vector_store == mock_vector_store
    
    def test_create_hybrid_provider(self):
        """Test creation of hybrid search provider with both dependencies."""
        # Arrange
        mock_pool = Mock()
        mock_vector_store = Mock()
        
        # Act
        provider = SearchFactory.create_hybrid_provider(mock_pool, mock_vector_store)
        
        # Assert
        assert isinstance(provider, HybridSearchProvider)
        assert isinstance(provider.bm25_provider, BM25Provider)
        assert isinstance(provider.vector_provider, VectorSearchProvider)
        assert provider.bm25_provider.db_provider == mock_pool
        assert provider.vector_provider._vector_store == mock_vector_store
    
    def test_create_search_provider_bm25(self):
        """Test creating BM25 provider via create_search_provider."""
        # Arrange
        mock_pool = Mock()
        
        # Act
        provider = SearchFactory.create_search_provider(
            search_type="bm25",
            postgres_pool=mock_pool
        )
        
        # Assert
        assert isinstance(provider, BM25Provider)
    
    def test_create_search_provider_vector(self):
        """Test creating vector provider via create_search_provider."""
        # Arrange
        mock_vector_store = Mock()
        
        # Act
        provider = SearchFactory.create_search_provider(
            search_type="vector",
            vector_store=mock_vector_store
        )
        
        # Assert
        assert isinstance(provider, VectorSearchProvider)
    
    def test_create_search_provider_hybrid(self):
        """Test creating hybrid provider via create_search_provider."""
        # Arrange
        mock_pool = Mock()
        mock_vector_store = Mock()
        
        # Act
        provider = SearchFactory.create_search_provider(
            search_type="hybrid",
            postgres_pool=mock_pool,
            vector_store=mock_vector_store
        )
        
        # Assert
        assert isinstance(provider, HybridSearchProvider)
    
    def test_create_search_provider_missing_postgres_pool(self):
        """Test that BM25 provider requires postgres_pool."""
        # Act & Assert
        with pytest.raises(ValueError, match="postgres_pool is required"):
            SearchFactory.create_search_provider(search_type="bm25")
    
    def test_create_search_provider_missing_vector_store(self):
        """Test that vector provider requires vector_store."""
        # Act & Assert
        with pytest.raises(ValueError, match="vector_store is required"):
            SearchFactory.create_search_provider(search_type="vector")
    
    def test_create_search_provider_hybrid_missing_dependencies(self):
        """Test that hybrid provider requires both dependencies."""
        # Mock pool but no vector store
        mock_pool = Mock()
        
        # Act & Assert
        with pytest.raises(ValueError, match="Both postgres_pool and vector_store are required"):
            SearchFactory.create_search_provider(
                search_type="hybrid",
                postgres_pool=mock_pool
            )
    
    def test_create_search_provider_unknown_type(self):
        """Test that unknown search types raise ValueError."""
        # Arrange
        mock_pool = Mock()
        mock_vector_store = Mock()
        
        # Act & Assert
        with pytest.raises(ValueError, match="Unknown search provider type: invalid"):
            SearchFactory.create_search_provider(
                search_type="invalid",
                postgres_pool=mock_pool,
                vector_store=mock_vector_store
            )
    
    def test_create_search_provider_default_from_config(self, monkeypatch):
        """Test that default search type is read from config."""
        # Arrange
        mock_pool = Mock()
        mock_vector_store = Mock()
        
        # Mock the settings at the factory module level
        from app.factory import search_factory
        from app.core.config import settings
        
        # Save original value
        original_search_type = settings.SEARCH_CONFIG.get("search_type", "hybrid")
        
        # Temporarily modify settings
        settings.SEARCH_CONFIG["search_type"] = "vector"
        
        try:
            # Act
            provider = SearchFactory.create_search_provider(
                postgres_pool=mock_pool,
                vector_store=mock_vector_store
            )
            
            # Assert
            assert isinstance(provider, VectorSearchProvider)
        finally:
            # Restore original value
            settings.SEARCH_CONFIG["search_type"] = original_search_type
