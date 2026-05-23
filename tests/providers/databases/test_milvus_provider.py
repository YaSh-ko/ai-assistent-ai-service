"""
Tests for Milvus Vector Store Provider.
Coverage target: 80%+
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from app.providers.databases.milvus_provider import MilvusProvider


@pytest.fixture
def mock_pymilvus():
    """Mock pymilvus module and its components."""
    mock_connections = MagicMock()
    mock_collection = MagicMock()
    mock_utility = MagicMock()
    
    # Setup default behaviors
    mock_connections.has_connection.return_value = False
    mock_utility.has_collection.return_value = False
    
    return {
        'connections': mock_connections,
        'Collection': MagicMock(return_value=mock_collection),
        'CollectionSchema': MagicMock(),
        'FieldSchema': MagicMock(),
        'DataType': MagicMock(
            VARCHAR=MagicMock(),
            FLOAT_VECTOR=MagicMock(),
            JSON=MagicMock()
        ),
        'utility': mock_utility,
        'collection_instance': mock_collection
    }


@pytest.fixture
def mock_settings():
    """Mock settings."""
    with patch('app.providers.databases.milvus_provider.settings') as mock:
        mock.MILVUS_HOST = "localhost"
        mock.MILVUS_PORT = 19530
        mock.MILVUS_USER = ""
        mock.MILVUS_PASSWORD = ""
        mock.EMBEDDING_CONFIG = {"dimension": 1024}
        mock.SEARCH_CONFIG = {"distance_metric": "cosine"}
        yield mock


class TestMilvusProviderInitialization:
    """Test MilvusProvider initialization."""
    
    def test_init_with_default_config(self, mock_pymilvus, mock_settings):
        """Test initialization with default configuration."""
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    
                    assert provider._host == "localhost"
                    assert provider._port == 19530
                    assert provider._collection_name == "chat_history"
                    assert provider._embedding_dim == 1024
                    assert provider._metric_type == "COSINE"
    
    def test_init_with_custom_config(self, mock_pymilvus, mock_settings):
        """Test initialization with custom configuration."""
        config = {
            "milvus_host": "custom-host",
            "milvus_port": 9999,
            "milvus_user": "admin",
            "milvus_password": "secret",
            "milvus_collection": "custom_collection",
            "embedding_dimension": 512
        }
        
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider(config)
                    
                    assert provider._host == "custom-host"
                    assert provider._port == 9999
                    assert provider._user == "admin"
                    assert provider._password == "secret"
                    assert provider._collection_name == "custom_collection"
                    assert provider._embedding_dim == 512
    
    def test_init_without_pymilvus(self):
        """Test initialization fails without pymilvus installed."""
        with patch.dict('sys.modules', {'pymilvus': None}):
            with patch('builtins.__import__', side_effect=ImportError):
                with pytest.raises(ImportError, match="pymilvus is not installed"):
                    MilvusProvider()
    
    def test_metric_type_mapping(self, mock_pymilvus, mock_settings):
        """Test distance metric mapping."""
        test_cases = [
            ("cosine", "COSINE"),
            ("l2", "L2"),
            ("ip", "IP"),
            ("unknown", "COSINE")  # Default fallback
        ]
        
        for metric, expected in test_cases:
            mock_settings.SEARCH_CONFIG = {"distance_metric": metric}
            
            with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
                with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                    with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                        provider = MilvusProvider()
                        assert provider._metric_type == expected


class TestConnect:
    """Test connection establishment."""
    
    def test_connect_without_auth(self, mock_pymilvus, mock_settings):
        """Test connection without authentication."""
        with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
            with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                provider = MilvusProvider()
                
                mock_pymilvus['connections'].connect.assert_called_once()
                call_kwargs = mock_pymilvus['connections'].connect.call_args[1]
                assert call_kwargs['host'] == "localhost"
                assert call_kwargs['port'] == 19530
                assert 'user' not in call_kwargs
    
    def test_connect_with_auth(self, mock_pymilvus, mock_settings):
        """Test connection with authentication."""
        config = {
            "milvus_user": "admin",
            "milvus_password": "secret"
        }
        
        with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
            with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                provider = MilvusProvider(config)
                
                call_kwargs = mock_pymilvus['connections'].connect.call_args[1]
                assert call_kwargs['user'] == "admin"
                assert call_kwargs['password'] == "secret"
    
    def test_connect_disconnects_existing(self, mock_pymilvus, mock_settings):
        """Test that existing connection is disconnected."""
        mock_pymilvus['connections'].has_connection.return_value = True
        
        with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
            with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                provider = MilvusProvider()
                
                mock_pymilvus['connections'].disconnect.assert_called_once_with("default")
    
    def test_connect_handles_errors(self, mock_pymilvus, mock_settings):
        """Test connection error handling."""
        mock_pymilvus['connections'].connect.side_effect = Exception("Connection failed")
        
        with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
            with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                with pytest.raises(Exception):
                    MilvusProvider()


class TestInitCollection:
    """Test collection initialization."""
    
    def test_init_loads_existing_collection(self, mock_pymilvus, mock_settings):
        """Test loading existing collection."""
        mock_pymilvus['utility'].has_collection.return_value = True
        
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                provider = MilvusProvider()
                
                mock_pymilvus['Collection'].assert_called_once_with("chat_history")
                mock_pymilvus['collection_instance'].load.assert_called_once()
    
    def test_init_creates_new_collection(self, mock_pymilvus, mock_settings):
        """Test creating new collection."""
        mock_pymilvus['utility'].has_collection.return_value = False
        
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                provider = MilvusProvider()
                
                # Verify schema fields were created
                assert mock_pymilvus['FieldSchema'].call_count >= 4
                
                # Verify collection was created
                mock_pymilvus['Collection'].assert_called_once()
                
                # Verify index was created
                mock_pymilvus['collection_instance'].create_index.assert_called_once()
                
                # Verify collection was loaded
                mock_pymilvus['collection_instance'].load.assert_called_once()


class TestAddDocuments:
    """Test adding documents."""
    
    @pytest.mark.asyncio
    async def test_add_documents_success(self, mock_pymilvus, mock_settings):
        """Test successful document addition."""
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    provider._collection = mock_pymilvus['collection_instance']
                    
                    documents = [
                        {"id": "doc1", "page_content": "Content 1", "metadata": {"key": "value1"}},
                        {"id": "doc2", "page_content": "Content 2", "metadata": {"key": "value2"}}
                    ]
                    embeddings = [[0.1, 0.2], [0.3, 0.4]]
                    
                    await provider.add_documents(documents, embeddings)
                    
                    mock_pymilvus['collection_instance'].insert.assert_called_once()
                    mock_pymilvus['collection_instance'].flush.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_add_documents_generates_ids(self, mock_pymilvus, mock_settings):
        """Test that IDs are generated if not provided."""
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    provider._collection = mock_pymilvus['collection_instance']
                    
                    documents = [
                        {"page_content": "Content without ID", "metadata": {}}
                    ]
                    embeddings = [[0.1, 0.2]]
                    
                    with patch('uuid.uuid4', return_value="generated-uuid"):
                        await provider.add_documents(documents, embeddings)
                    
                    # Verify insert was called with generated ID
                    call_args = mock_pymilvus['collection_instance'].insert.call_args[0][0]
                    assert "generated-uuid" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_add_documents_empty_lists(self, mock_pymilvus, mock_settings):
        """Test adding empty document lists."""
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    
                    await provider.add_documents([], [])
                    
                    mock_pymilvus['collection_instance'].insert.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_add_documents_mismatched_lengths(self, mock_pymilvus, mock_settings):
        """Test error when documents and embeddings lengths don't match."""
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    
                    documents = [{"id": "doc1", "page_content": "Content"}]
                    embeddings = [[0.1], [0.2]]  # Mismatched length
                    
                    with pytest.raises(ValueError, match="Documents count"):
                        await provider.add_documents(documents, embeddings)
    
    @pytest.mark.asyncio
    async def test_add_documents_handles_errors(self, mock_pymilvus, mock_settings):
        """Test error handling during document addition."""
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    provider._collection = mock_pymilvus['collection_instance']
                    
                    mock_pymilvus['collection_instance'].insert.side_effect = Exception("Insert failed")
                    
                    documents = [{"id": "doc1", "page_content": "Content", "metadata": {}}]
                    embeddings = [[0.1, 0.2]]
                    
                    with pytest.raises(Exception):
                        await provider.add_documents(documents, embeddings)


class TestSimilaritySearch:
    """Test similarity search."""
    
    @pytest.mark.asyncio
    async def test_similarity_search_without_filter(self, mock_pymilvus, mock_settings):
        """Test similarity search without filters."""
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    provider._collection = mock_pymilvus['collection_instance']
                    
                    # Mock search results
                    mock_hit = MagicMock()
                    mock_hit.entity.get.side_effect = lambda k, default=None: {
                        "id": "doc1",
                        "page_content": "Content",
                        "metadata": {"key": "value"}
                    }.get(k, default)
                    mock_hit.score = 0.95
                    
                    mock_pymilvus['collection_instance'].search.return_value = [[mock_hit]]
                    
                    results = await provider.similarity_search([0.1, 0.2], k=5)
                    
                    assert len(results) == 1
                    assert results[0]["id"] == "doc1"
                    assert results[0]["score"] == 0.95
    
    @pytest.mark.asyncio
    async def test_similarity_search_with_string_filter(self, mock_pymilvus, mock_settings):
        """Test similarity search with string filter."""
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    provider._collection = mock_pymilvus['collection_instance']
                    
                    mock_pymilvus['collection_instance'].search.return_value = [[]]
                    
                    filter_dict = {"user_id": "user123"}
                    await provider.similarity_search([0.1, 0.2], k=5, filter=filter_dict)
                    
                    # Verify filter expression was built
                    call_kwargs = mock_pymilvus['collection_instance'].search.call_args[1]
                    assert "metadata['user_id'] == 'user123'" in call_kwargs['expr']
    
    @pytest.mark.asyncio
    async def test_similarity_search_with_numeric_filter(self, mock_pymilvus, mock_settings):
        """Test similarity search with numeric filter."""
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    provider._collection = mock_pymilvus['collection_instance']
                    
                    mock_pymilvus['collection_instance'].search.return_value = [[]]
                    
                    filter_dict = {"count": 42}
                    await provider.similarity_search([0.1, 0.2], k=5, filter=filter_dict)
                    
                    call_kwargs = mock_pymilvus['collection_instance'].search.call_args[1]
                    assert "metadata['count'] == 42" in call_kwargs['expr']
    
    @pytest.mark.asyncio
    async def test_similarity_search_with_bool_filter(self, mock_pymilvus, mock_settings):
        """Test similarity search with boolean filter."""
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    provider._collection = mock_pymilvus['collection_instance']
                    
                    mock_pymilvus['collection_instance'].search.return_value = [[]]
                    
                    filter_dict = {"is_active": True}
                    await provider.similarity_search([0.1, 0.2], k=5, filter=filter_dict)
                    
                    call_kwargs = mock_pymilvus['collection_instance'].search.call_args[1]
                    assert "metadata['is_active'] == true" in call_kwargs['expr']
    
    @pytest.mark.asyncio
    async def test_similarity_search_handles_errors(self, mock_pymilvus, mock_settings):
        """Test error handling during similarity search."""
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    provider._collection = mock_pymilvus['collection_instance']
                    
                    mock_pymilvus['collection_instance'].search.side_effect = Exception("Search failed")
                    
                    with pytest.raises(Exception):
                        await provider.similarity_search([0.1, 0.2])


class TestReset:
    """Test collection reset."""
    
    @pytest.mark.asyncio
    async def test_reset_existing_collection(self, mock_pymilvus, mock_settings):
        """Test resetting existing collection."""
        mock_pymilvus['utility'].has_collection.return_value = True
        
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection') as mock_init:
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    provider._collection = mock_pymilvus['collection_instance']
                    
                    # Reset call count
                    mock_init.reset_mock()
                    
                    await provider.reset()
                    
                    mock_pymilvus['collection_instance'].drop.assert_called_once()
                    # _init_collection should be called again
                    assert mock_init.call_count == 1
    
    @pytest.mark.asyncio
    async def test_reset_handles_errors(self, mock_pymilvus, mock_settings):
        """Test error handling during reset."""
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    
                    mock_pymilvus['utility'].has_collection.side_effect = Exception("Reset failed")
                    
                    with pytest.raises(Exception):
                        await provider.reset()


class TestDeleteDocuments:
    """Test document deletion."""
    
    @pytest.mark.asyncio
    async def test_delete_documents_success(self, mock_pymilvus, mock_settings):
        """Test successful document deletion."""
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    provider._collection = mock_pymilvus['collection_instance']
                    
                    ids = ["doc1", "doc2", "doc3"]
                    await provider.delete_documents(ids)
                    
                    mock_pymilvus['collection_instance'].delete.assert_called_once()
                    call_args = mock_pymilvus['collection_instance'].delete.call_args[0][0]
                    assert "doc1" in call_args
                    assert "doc2" in call_args
                    assert "doc3" in call_args
                    
                    mock_pymilvus['collection_instance'].flush.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_documents_empty_list(self, mock_pymilvus, mock_settings):
        """Test deleting with empty ID list."""
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    
                    await provider.delete_documents([])
                    
                    mock_pymilvus['collection_instance'].delete.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_delete_documents_handles_errors(self, mock_pymilvus, mock_settings):
        """Test error handling during deletion."""
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    provider._collection = mock_pymilvus['collection_instance']
                    
                    mock_pymilvus['collection_instance'].delete.side_effect = Exception("Delete failed")
                    
                    with pytest.raises(Exception):
                        await provider.delete_documents(["doc1"])


class TestGetByFilter:
    """Test getting documents by filter."""
    
    @pytest.mark.asyncio
    async def test_get_by_filter_success(self, mock_pymilvus, mock_settings):
        """Test successful filter query."""
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    provider._collection = mock_pymilvus['collection_instance']
                    
                    mock_pymilvus['collection_instance'].query.return_value = [
                        {"id": "doc1", "page_content": "Content", "metadata": {"key": "value"}}
                    ]
                    
                    results = await provider.get_by_filter({"user_id": "user123"})
                    
                    assert len(results) == 1
                    assert results[0]["id"] == "doc1"
    
    @pytest.mark.asyncio
    async def test_get_by_filter_multiple_conditions(self, mock_pymilvus, mock_settings):
        """Test filter with multiple conditions."""
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    provider._collection = mock_pymilvus['collection_instance']
                    
                    mock_pymilvus['collection_instance'].query.return_value = []
                    
                    filter_dict = {"user_id": "user123", "count": 5, "active": True}
                    await provider.get_by_filter(filter_dict)
                    
                    call_args = mock_pymilvus['collection_instance'].query.call_args[1]
                    expr = call_args['expr']
                    assert "user_id" in expr
                    assert "count" in expr
                    assert "active" in expr
                    assert " and " in expr
    
    @pytest.mark.asyncio
    async def test_get_by_filter_handles_errors(self, mock_pymilvus, mock_settings):
        """Test error handling during filter query."""
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    provider._collection = mock_pymilvus['collection_instance']
                    
                    mock_pymilvus['collection_instance'].query.side_effect = Exception("Query failed")
                    
                    with pytest.raises(Exception):
                        await provider.get_by_filter({"key": "value"})


class TestClose:
    """Test connection closing."""
    
    def test_close_disconnects(self, mock_pymilvus, mock_settings):
        """Test that close disconnects from Milvus."""
        mock_pymilvus['connections'].has_connection.return_value = True
        
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    
                    provider.close()
                    
                    mock_pymilvus['connections'].disconnect.assert_called_with("default")
    
    def test_close_no_connection(self, mock_pymilvus, mock_settings):
        """Test close when no connection exists."""
        mock_pymilvus['connections'].has_connection.return_value = False
        
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    
                    provider.close()
                    
                    # Should not raise error
                    mock_pymilvus['connections'].disconnect.assert_not_called()
    
    def test_close_handles_errors(self, mock_pymilvus, mock_settings):
        """Test error handling during close."""
        mock_pymilvus['connections'].has_connection.return_value = True
        mock_pymilvus['connections'].disconnect.side_effect = Exception("Disconnect failed")
        
        with patch('app.providers.databases.milvus_provider.MilvusProvider._connect'):
            with patch('app.providers.databases.milvus_provider.MilvusProvider._init_collection'):
                with patch.dict('sys.modules', {'pymilvus': MagicMock(**mock_pymilvus)}):
                    provider = MilvusProvider()
                    
                    # Should not raise exception
                    provider.close()
