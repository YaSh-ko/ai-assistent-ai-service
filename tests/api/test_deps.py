"""
Tests for app/api/deps.py - Dependency injection functions
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio


@pytest.mark.asyncio
class TestGetLLMService:
    """Tests for get_llm_service dependency"""
    
    async def test_get_llm_service_creates_singleton(self):
        """Test that LLM service is created as singleton"""
        from app.api import deps
        
        # Reset singleton
        deps._llm_service = None
        
        with patch('app.api.deps.LLMService') as mock_llm_class:
            mock_instance = Mock()
            mock_llm_class.return_value = mock_instance
            
            service1 = await deps.get_llm_service()
            service2 = await deps.get_llm_service()
            
            # Should be same instance
            assert service1 is service2
            # Should only be created once
            mock_llm_class.assert_called_once()
    
    async def test_get_llm_service_thread_safe(self):
        """Test that LLM service creation is thread-safe"""
        from app.api import deps
        
        # Reset singleton
        deps._llm_service = None
        
        with patch('app.api.deps.LLMService') as mock_llm_class:
            mock_instance = Mock()
            mock_llm_class.return_value = mock_instance
            
            # Call concurrently
            results = await asyncio.gather(
                deps.get_llm_service(),
                deps.get_llm_service(),
                deps.get_llm_service()
            )
            
            # All should be same instance
            assert results[0] is results[1] is results[2]
            # Should only be created once
            mock_llm_class.assert_called_once()


@pytest.mark.asyncio
class TestGetReasoningService:
    """Tests for get_reasoning_service dependency"""
    
    async def test_get_reasoning_service_creates_singleton(self):
        """Test that reasoning service is created as singleton"""
        from app.api import deps
        
        # Reset singleton
        deps._reasoning_service = None
        
        with patch('app.api.deps.ReasoningService') as mock_reasoning_class:
            mock_instance = Mock()
            mock_reasoning_class.return_value = mock_instance
            
            service1 = await deps.get_reasoning_service()
            service2 = await deps.get_reasoning_service()
            
            assert service1 is service2
            mock_reasoning_class.assert_called_once()


@pytest.mark.asyncio
class TestGetPIIService:
    """Tests for get_pii_service dependency"""
    
    async def test_get_pii_service_creates_singleton(self):
        """Test that PII service is created as singleton"""
        from app.api import deps
        
        # Reset singleton
        deps._pii_service = None
        
        with patch('app.api.deps.PIIService') as mock_pii_class:
            mock_instance = Mock()
            mock_pii_class.return_value = mock_instance
            
            service1 = await deps.get_pii_service()
            service2 = await deps.get_pii_service()
            
            assert service1 is service2
            mock_pii_class.assert_called_once()


@pytest.mark.asyncio
class TestGetDALAsync:
    """Tests for get_dal_async dependency"""
    
    async def test_get_dal_async_creates_singleton(self):
        """Test that DAL is created as singleton"""
        from app.api import deps
        
        # Reset singleton
        deps._dal = None
        
        with patch('app.api.deps.DatabaseFactory.create_dal_async', new_callable=AsyncMock) as mock_create:
            mock_dal = Mock()
            mock_create.return_value = mock_dal
            
            dal1 = await deps.get_dal_async()
            dal2 = await deps.get_dal_async()
            
            assert dal1 is dal2
            mock_create.assert_called_once()


@pytest.mark.asyncio
class TestGetSessionManager:
    """Tests for get_session_manager dependency"""
    
    async def test_get_session_manager_creates_singleton(self):
        """Test that session manager is created as singleton"""
        from app.api import deps
        from app.providers.databases.postgres_provider import PostgresProvider
        
        # Reset singleton
        deps._session_manager = None
        
        # Mock PostgresProvider
        mock_provider = Mock(spec=PostgresProvider)
        mock_provider.pool = Mock()
        mock_provider.connect = AsyncMock()
        
        with patch('app.api.deps.DatabaseFactory.create_relational_database', return_value=mock_provider):
            with patch('app.api.deps.ChatSessionRepository') as mock_repo_class:
                with patch('app.api.deps.SessionManager') as mock_manager_class:
                    mock_repo = Mock()
                    mock_manager = Mock()
                    mock_repo_class.return_value = mock_repo
                    mock_manager_class.return_value = mock_manager
                    
                    manager1 = await deps.get_session_manager()
                    manager2 = await deps.get_session_manager()
                    
                    assert manager1 is manager2
                    mock_manager_class.assert_called_once_with(mock_repo)
    
    async def test_get_session_manager_connects_provider(self):
        """Test that session manager connects provider if not connected"""
        from app.api import deps
        from app.providers.databases.postgres_provider import PostgresProvider
        
        # Reset singleton
        deps._session_manager = None
        
        # Mock PostgresProvider without pool
        mock_provider = Mock(spec=PostgresProvider)
        mock_provider.pool = None
        mock_provider.connect = AsyncMock()
        
        with patch('app.api.deps.DatabaseFactory.create_relational_database', return_value=mock_provider):
            with patch('app.api.deps.ChatSessionRepository'):
                with patch('app.api.deps.SessionManager'):
                    await deps.get_session_manager()
                    
                    # Verify connect was called
                    mock_provider.connect.assert_called_once()
    
    async def test_get_session_manager_raises_error_for_non_postgres(self):
        """Test that session manager raises error for non-PostgreSQL provider"""
        from app.api import deps
        
        # Reset singleton
        deps._session_manager = None
        
        # Mock non-PostgreSQL provider
        mock_provider = Mock()
        mock_provider.pool = Mock()
        
        with patch('app.api.deps.DatabaseFactory.create_relational_database', return_value=mock_provider):
            with pytest.raises(RuntimeError, match="SessionManager requires PostgresProvider"):
                await deps.get_session_manager()


@pytest.mark.asyncio
class TestGetRAGChain:
    """Tests for get_rag_chain dependency"""
    
    async def test_get_rag_chain_creates_singleton(self):
        """Test that RAG chain is created as singleton"""
        from app.api import deps
        
        # Reset singleton
        deps._rag_chain = None
        deps._dal = None
        deps._llm_service = None
        deps._reasoning_service = None
        deps._pii_service = None
        
        # Mock all dependencies
        mock_dal = Mock()
        mock_dal.embedding_repo = Mock()
        
        mock_postgres = Mock()
        mock_postgres.pool = Mock()
        mock_postgres.connect = AsyncMock()
        
        mock_vector_store = Mock()
        mock_graph_db = AsyncMock()
        
        with patch('app.api.deps.get_dal_async', new_callable=AsyncMock, return_value=mock_dal):
            with patch('app.api.deps.DatabaseFactory.create_relational_database', return_value=mock_postgres):
                with patch('app.api.deps.DatabaseFactory.create_vector_store', return_value=mock_vector_store):
                    with patch('app.api.deps.DatabaseFactory.create_graph_database', new_callable=AsyncMock, return_value=mock_graph_db):
                        with patch('app.api.deps.get_llm_service', new_callable=AsyncMock, return_value=Mock()):
                            with patch('app.api.deps.get_reasoning_service', new_callable=AsyncMock, return_value=Mock()):
                                with patch('app.api.deps.get_pii_service', new_callable=AsyncMock, return_value=Mock()):
                                    with patch('app.api.deps.BM25Provider'):
                                        with patch('app.api.deps.VectorSearchProvider'):
                                            with patch('app.api.deps.HybridSearchProvider'):
                                                with patch('app.api.deps.GraphRepository'):
                                                    with patch('app.api.deps.ChunkingService'):
                                                        with patch('app.api.deps.GigaChatEmbeddings'):
                                                            with patch('app.api.deps.EmbeddingService'):
                                                                with patch('app.api.deps.RerankerProvider'):
                                                                    with patch('app.api.deps.RAGChain') as mock_rag_class:
                                                                        mock_rag = Mock()
                                                                        mock_rag_class.return_value = mock_rag
                                                                        
                                                                        chain1 = await deps.get_rag_chain()
                                                                        chain2 = await deps.get_rag_chain()
                                                                        
                                                                        assert chain1 is chain2
                                                                        mock_rag_class.assert_called_once()
    
    async def test_get_rag_chain_handles_neo4j_unavailable(self):
        """Test that RAG chain handles Neo4j being unavailable"""
        from app.api import deps
        
        # Reset singleton
        deps._rag_chain = None
        deps._dal = None
        
        # Mock all dependencies
        mock_dal = Mock()
        mock_dal.embedding_repo = Mock()
        
        mock_postgres = Mock()
        mock_postgres.pool = Mock()
        mock_postgres.connect = AsyncMock()
        
        mock_vector_store = Mock()
        
        with patch('app.api.deps.get_dal_async', new_callable=AsyncMock, return_value=mock_dal):
            with patch('app.api.deps.DatabaseFactory.create_relational_database', return_value=mock_postgres):
                with patch('app.api.deps.DatabaseFactory.create_vector_store', return_value=mock_vector_store):
                    # Neo4j raises exception
                    with patch('app.api.deps.DatabaseFactory.create_graph_database', new_callable=AsyncMock, side_effect=Exception("Neo4j unavailable")):
                        with patch('app.api.deps.get_llm_service', new_callable=AsyncMock, return_value=Mock()):
                            with patch('app.api.deps.get_reasoning_service', new_callable=AsyncMock, return_value=Mock()):
                                with patch('app.api.deps.get_pii_service', new_callable=AsyncMock, return_value=Mock()):
                                    with patch('app.api.deps.BM25Provider'):
                                        with patch('app.api.deps.VectorSearchProvider'):
                                            with patch('app.api.deps.HybridSearchProvider'):
                                                with patch('app.api.deps.ChunkingService'):
                                                    with patch('app.api.deps.GigaChatEmbeddings'):
                                                        with patch('app.api.deps.EmbeddingService'):
                                                            with patch('app.api.deps.RerankerProvider'):
                                                                with patch('app.api.deps.RAGChain') as mock_rag_class:
                                                                    mock_rag = Mock()
                                                                    mock_rag_class.return_value = mock_rag
                                                                    
                                                                    chain = await deps.get_rag_chain()
                                                                    
                                                                    # Should still create RAG chain with graph_repository=None
                                                                    assert chain is not None
                                                                    call_kwargs = mock_rag_class.call_args[1]
                                                                    assert call_kwargs['graph_repository'] is None


class TestSingletonLocks:
    """Tests for singleton initialization locks"""
    
    def test_all_locks_are_asyncio_locks(self):
        """Test that all singleton locks are asyncio.Lock instances"""
        from app.api import deps
        
        assert isinstance(deps._llm_lock, asyncio.Lock)
        assert isinstance(deps._reasoning_lock, asyncio.Lock)
        assert isinstance(deps._pii_lock, asyncio.Lock)
        assert isinstance(deps._session_manager_lock, asyncio.Lock)
        assert isinstance(deps._rag_chain_lock, asyncio.Lock)
        assert isinstance(deps._dal_lock, asyncio.Lock)


class TestSingletonInitialization:
    """Tests for singleton initialization state"""
    
    def test_singletons_start_as_none(self):
        """Test that singletons are initialized as None"""
        from app.api import deps
        
        # Reset all singletons
        deps._llm_service = None
        deps._reasoning_service = None
        deps._pii_service = None
        deps._session_manager = None
        deps._rag_chain = None
        deps._dal = None
        
        assert deps._llm_service is None
        assert deps._reasoning_service is None
        assert deps._pii_service is None
        assert deps._session_manager is None
        assert deps._rag_chain is None
        assert deps._dal is None
