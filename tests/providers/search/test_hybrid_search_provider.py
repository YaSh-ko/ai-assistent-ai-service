"""
Tests for HybridSearchProvider.
Coverage target: 80%+
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.providers.search.hybrid_search_provider import (
    HybridSearchProvider,
    normalize_bm25_scores,
    normalize_vector_scores
)


class TestNormalizeBM25Scores:
    """Test BM25 score normalization."""
    
    def test_normalize_empty_results(self):
        """Test normalization with empty results."""
        result = normalize_bm25_scores([])
        assert result == []
    
    def test_normalize_single_result(self):
        """Test normalization with single result."""
        results = [{'bm25_score': 10.5}]
        normalized = normalize_bm25_scores(results)
        
        assert normalized[0]['normalized_score'] == 1.0
    
    def test_normalize_multiple_results(self):
        """Test normalization with multiple results."""
        results = [
            {'bm25_score': 10.0},
            {'bm25_score': 5.0},
            {'bm25_score': 0.0}
        ]
        normalized = normalize_bm25_scores(results)
        
        assert normalized[0]['normalized_score'] == 1.0
        assert normalized[1]['normalized_score'] == 0.5
        assert normalized[2]['normalized_score'] == 0.0
    
    def test_normalize_same_scores(self):
        """Test normalization when all scores are the same."""
        results = [
            {'bm25_score': 5.0},
            {'bm25_score': 5.0},
            {'bm25_score': 5.0}
        ]
        normalized = normalize_bm25_scores(results)
        
        assert all(r['normalized_score'] == 1.0 for r in normalized)


class TestNormalizeVectorScores:
    """Test vector score normalization."""
    
    def test_normalize_empty_results(self):
        """Test normalization with empty results."""
        result = normalize_vector_scores([])
        assert result == []
    
    def test_normalize_single_result(self):
        """Test normalization with single result."""
        results = [{'score': 0.95}]
        normalized = normalize_vector_scores(results)
        
        assert normalized[0]['normalized_score'] == 1.0
    
    def test_normalize_multiple_results(self):
        """Test normalization with multiple results."""
        results = [
            {'score': 1.0},
            {'score': 0.5},
            {'score': 0.0}
        ]
        normalized = normalize_vector_scores(results)
        
        assert normalized[0]['normalized_score'] == 1.0
        assert normalized[1]['normalized_score'] == 0.5
        assert normalized[2]['normalized_score'] == 0.0
    
    def test_normalize_same_scores(self):
        """Test normalization when all scores are the same."""
        results = [
            {'score': 0.8},
            {'score': 0.8},
            {'score': 0.8}
        ]
        normalized = normalize_vector_scores(results)
        
        assert all(r['normalized_score'] == 1.0 for r in normalized)


@pytest.fixture
def mock_bm25_provider():
    """Mock BM25 provider."""
    provider = MagicMock()
    provider.search = AsyncMock()
    return provider


@pytest.fixture
def mock_vector_provider():
    """Mock vector provider."""
    provider = MagicMock()
    provider.search = AsyncMock()
    return provider


@pytest.fixture
def mock_settings():
    """Mock settings."""
    with patch('app.providers.search.hybrid_search_provider.settings') as mock:
        mock.SEARCH_CONFIG = {
            'bm25_weight': 0.3,
            'vector_weight': 0.7
        }
        yield mock


@pytest.fixture
def hybrid_provider(mock_bm25_provider, mock_vector_provider, mock_settings):
    """Create HybridSearchProvider instance."""
    return HybridSearchProvider(mock_bm25_provider, mock_vector_provider)


class TestHybridSearchProvider:
    """Test HybridSearchProvider."""
    
    @pytest.mark.asyncio
    async def test_search_combines_results(self, hybrid_provider, mock_bm25_provider, mock_vector_provider):
        """Test that search combines BM25 and vector results."""
        bm25_results = [
            {
                'id': 'doc1',
                'title': 'Document 1',
                'description': 'Content 1',
                'bm25_score': 10.0,
                'user_id': 'user123',
                'event_date': '2025-01-15',
                'average_intensity': 0.5,
                'created_at': '2025-01-15',
                'updated_at': '2025-01-15'
            }
        ]
        
        vector_results = [
            {
                'metadata': {'entry_id': 'doc1'},
                'page_content': 'Content 1',
                'score': 0.9
            }
        ]
        
        mock_bm25_provider.search.return_value = bm25_results
        mock_vector_provider.search.return_value = vector_results
        
        results = await hybrid_provider.search(
            query="test query",
            query_embedding=[0.1, 0.2, 0.3],
            k=10
        )
        
        assert len(results) > 0
        assert results[0]['id'] == 'doc1'
        assert results[0]['source'] == 'hybrid'
        assert 'final_score' in results[0]
    
    @pytest.mark.asyncio
    async def test_search_bm25_only(self, hybrid_provider, mock_bm25_provider, mock_vector_provider):
        """Test search with only BM25 results."""
        bm25_results = [
            {
                'id': 'doc1',
                'title': 'Document 1',
                'description': 'Content 1',
                'bm25_score': 10.0,
                'user_id': 'user123',
                'event_date': '2025-01-15',
                'average_intensity': 0.5,
                'created_at': '2025-01-15',
                'updated_at': '2025-01-15'
            }
        ]
        
        mock_bm25_provider.search.return_value = bm25_results
        mock_vector_provider.search.return_value = []
        
        results = await hybrid_provider.search(
            query="test query",
            query_embedding=[0.1, 0.2, 0.3],
            k=10
        )
        
        assert len(results) == 1
        assert results[0]['source'] == 'bm25'
        assert results[0]['vector_score'] == 0
    
    @pytest.mark.asyncio
    async def test_search_vector_only(self, hybrid_provider, mock_bm25_provider, mock_vector_provider):
        """Test search with only vector results."""
        vector_results = [
            {
                'metadata': {'entry_id': 'doc2'},
                'page_content': 'Content 2',
                'score': 0.85
            }
        ]
        
        mock_bm25_provider.search.return_value = []
        mock_vector_provider.search.return_value = vector_results
        
        results = await hybrid_provider.search(
            query="test query",
            query_embedding=[0.1, 0.2, 0.3],
            k=10
        )
        
        assert len(results) == 1
        assert results[0]['source'] == 'vector'
        assert results[0]['bm25_score'] == 0
    
    @pytest.mark.asyncio
    async def test_search_sorts_by_final_score(self, hybrid_provider, mock_bm25_provider, mock_vector_provider):
        """Test that results are sorted by final score."""
        bm25_results = [
            {
                'id': 'doc1',
                'title': 'Doc 1',
                'description': 'Content',
                'bm25_score': 5.0,
                'user_id': 'user123',
                'event_date': '2025-01-15',
                'average_intensity': 0.5,
                'created_at': '2025-01-15',
                'updated_at': '2025-01-15'
            },
            {
                'id': 'doc2',
                'title': 'Doc 2',
                'description': 'Content',
                'bm25_score': 10.0,
                'user_id': 'user123',
                'event_date': '2025-01-15',
                'average_intensity': 0.5,
                'created_at': '2025-01-15',
                'updated_at': '2025-01-15'
            }
        ]
        
        vector_results = [
            {'metadata': {'entry_id': 'doc1'}, 'page_content': 'Content', 'score': 0.9},
            {'metadata': {'entry_id': 'doc2'}, 'page_content': 'Content', 'score': 0.5}
        ]
        
        mock_bm25_provider.search.return_value = bm25_results
        mock_vector_provider.search.return_value = vector_results
        
        results = await hybrid_provider.search(
            query="test",
            query_embedding=[0.1, 0.2],
            k=10
        )
        
        # Results should be sorted by final_score descending
        assert results[0]['final_score'] >= results[1]['final_score']
    
    @pytest.mark.asyncio
    async def test_search_respects_k_limit(self, hybrid_provider, mock_bm25_provider, mock_vector_provider):
        """Test that search respects k limit."""
        bm25_results = [
            {
                'id': f'doc{i}',
                'title': f'Doc {i}',
                'description': 'Content',
                'bm25_score': 10.0 - i,
                'user_id': 'user123',
                'event_date': '2025-01-15',
                'average_intensity': 0.5,
                'created_at': '2025-01-15',
                'updated_at': '2025-01-15'
            }
            for i in range(20)
        ]
        
        mock_bm25_provider.search.return_value = bm25_results
        mock_vector_provider.search.return_value = []
        
        results = await hybrid_provider.search(
            query="test",
            query_embedding=[0.1],
            k=5
        )
        
        assert len(results) == 5
    
    @pytest.mark.asyncio
    async def test_search_with_top_k_override(self, hybrid_provider, mock_bm25_provider, mock_vector_provider):
        """Test search with top_k parameter override."""
        mock_bm25_provider.search.return_value = []
        mock_vector_provider.search.return_value = []
        
        await hybrid_provider.search(
            query="test",
            query_embedding=[0.1],
            k=10,
            top_k=50
        )
        
        # Verify providers were called with top_k=50
        mock_bm25_provider.search.assert_called_once()
        call_kwargs = mock_bm25_provider.search.call_args[1]
        assert call_kwargs['k'] == 50
    
    @pytest.mark.asyncio
    async def test_search_with_user_filter(self, hybrid_provider, mock_bm25_provider, mock_vector_provider):
        """Test search with user_id filter."""
        mock_bm25_provider.search.return_value = []
        mock_vector_provider.search.return_value = []
        
        await hybrid_provider.search(
            query="test",
            query_embedding=[0.1],
            k=10,
            user_id="user123"
        )
        
        # Verify user_id was passed to providers
        bm25_call_kwargs = mock_bm25_provider.search.call_args[1]
        assert bm25_call_kwargs['user_id'] == "user123"
        
        vector_call_kwargs = mock_vector_provider.search.call_args[1]
        assert vector_call_kwargs['user_id'] == "user123"
    
    @pytest.mark.asyncio
    async def test_search_calculates_weighted_score(self, hybrid_provider, mock_bm25_provider, mock_vector_provider):
        """Test that final score uses configured weights."""
        bm25_results = [
            {
                'id': 'doc1',
                'title': 'Doc',
                'description': 'Content',
                'bm25_score': 10.0,
                'user_id': 'user123',
                'event_date': '2025-01-15',
                'average_intensity': 0.5,
                'created_at': '2025-01-15',
                'updated_at': '2025-01-15'
            }
        ]
        
        vector_results = [
            {'metadata': {'entry_id': 'doc1'}, 'page_content': 'Content', 'score': 1.0}
        ]
        
        mock_bm25_provider.search.return_value = bm25_results
        mock_vector_provider.search.return_value = vector_results
        
        results = await hybrid_provider.search(
            query="test",
            query_embedding=[0.1],
            k=10
        )
        
        # With weights 0.3 and 0.7, and both normalized scores at 1.0
        # final_score should be 0.3 * 1.0 + 0.7 * 1.0 = 1.0
        assert results[0]['final_score'] == pytest.approx(1.0)
    
    @pytest.mark.asyncio
    async def test_search_empty_results(self, hybrid_provider, mock_bm25_provider, mock_vector_provider):
        """Test search with no results from either provider."""
        mock_bm25_provider.search.return_value = []
        mock_vector_provider.search.return_value = []
        
        results = await hybrid_provider.search(
            query="test",
            query_embedding=[0.1],
            k=10
        )
        
        assert results == []
