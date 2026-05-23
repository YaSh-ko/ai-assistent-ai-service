"""
Tests for app/providers/embeddings/gigachat_embeddings.py
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import httpx
from app.providers.embeddings.gigachat_embeddings import GigaChatEmbeddings


class TestGigaChatEmbeddingsInit:
    """Tests for GigaChatEmbeddings initialization"""
    
    @patch('app.providers.embeddings.gigachat_embeddings.settings')
    def test_init_with_credentials(self, mock_settings):
        """Test initialization with GIGACHAT_CREDENTIALS"""
        mock_settings.GIGACHAT_CREDENTIALS = "test_credentials"
        mock_settings.GIGACHAT_CLIENT_ID = ""
        mock_settings.GIGACHAT_CLIENT_SECRET = ""
        mock_settings.GIGACHAT_SCOPE = "GIGACHAT_API_PERS"
        
        embeddings = GigaChatEmbeddings()
        
        assert embeddings.credentials == "test_credentials"
        assert embeddings.scope == "GIGACHAT_API_PERS"
        assert embeddings.auth_url == "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        assert embeddings.embed_url == "https://gigachat.devices.sberbank.ru/api/v1/embeddings"
    
    @patch('app.providers.embeddings.gigachat_embeddings.settings')
    def test_init_with_client_id_secret(self, mock_settings):
        """Test initialization with CLIENT_ID and CLIENT_SECRET"""
        mock_settings.GIGACHAT_CREDENTIALS = ""
        mock_settings.GIGACHAT_CLIENT_ID = "test_client_id"
        mock_settings.GIGACHAT_CLIENT_SECRET = "test_secret"
        mock_settings.GIGACHAT_SCOPE = "GIGACHAT_API_PERS"
        
        embeddings = GigaChatEmbeddings()
        
        assert embeddings.client_id == "test_client_id"
        assert embeddings.client_secret == "test_secret"
    
    @patch('app.providers.embeddings.gigachat_embeddings.settings')
    def test_init_without_credentials_raises_error(self, mock_settings):
        """Test initialization without any credentials raises ValueError"""
        mock_settings.GIGACHAT_CREDENTIALS = ""
        mock_settings.GIGACHAT_CLIENT_ID = ""
        mock_settings.GIGACHAT_CLIENT_SECRET = ""
        mock_settings.GIGACHAT_SCOPE = "GIGACHAT_API_PERS"
        
        with pytest.raises(ValueError, match="Either GIGACHAT_CREDENTIALS or"):
            GigaChatEmbeddings()
    
    @patch('app.providers.embeddings.gigachat_embeddings.settings')
    def test_init_with_partial_client_credentials_raises_error(self, mock_settings):
        """Test initialization with only CLIENT_ID (no SECRET) raises ValueError"""
        mock_settings.GIGACHAT_CREDENTIALS = ""
        mock_settings.GIGACHAT_CLIENT_ID = "test_client_id"
        mock_settings.GIGACHAT_CLIENT_SECRET = ""
        mock_settings.GIGACHAT_SCOPE = "GIGACHAT_API_PERS"
        
        with pytest.raises(ValueError, match="Either GIGACHAT_CREDENTIALS or"):
            GigaChatEmbeddings()


@pytest.mark.asyncio
class TestGigaChatEmbeddingsGetToken:
    """Tests for _get_token method"""
    
    @patch('app.providers.embeddings.gigachat_embeddings.settings')
    async def test_get_token_with_credentials(self, mock_settings):
        """Test token retrieval with pre-encoded credentials"""
        mock_settings.GIGACHAT_CREDENTIALS = "test_credentials"
        mock_settings.GIGACHAT_CLIENT_ID = ""
        mock_settings.GIGACHAT_CLIENT_SECRET = ""
        mock_settings.GIGACHAT_SCOPE = "GIGACHAT_API_PERS"
        
        embeddings = GigaChatEmbeddings()
        
        # Mock httpx client
        mock_response = Mock()
        mock_response.json.return_value = {"access_token": "test_token_123"}
        mock_response.raise_for_status = Mock()
        
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            token = await embeddings._get_token()
        
        assert token == "test_token_123"
        assert embeddings._access_token == "test_token_123"
        
        # Verify request was made with correct headers
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "Authorization" in call_args[1]["headers"]
        assert call_args[1]["headers"]["Authorization"] == "Basic test_credentials"
    
    @patch('app.providers.embeddings.gigachat_embeddings.settings')
    async def test_get_token_with_client_id_secret(self, mock_settings):
        """Test token retrieval with CLIENT_ID and CLIENT_SECRET"""
        mock_settings.GIGACHAT_CREDENTIALS = ""
        mock_settings.GIGACHAT_CLIENT_ID = "client_id"
        mock_settings.GIGACHAT_CLIENT_SECRET = "client_secret"
        mock_settings.GIGACHAT_SCOPE = "GIGACHAT_API_PERS"
        
        embeddings = GigaChatEmbeddings()
        
        # Mock httpx client
        mock_response = Mock()
        mock_response.json.return_value = {"access_token": "token_from_client_creds"}
        mock_response.raise_for_status = Mock()
        
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            token = await embeddings._get_token()
        
        assert token == "token_from_client_creds"
        
        # Verify Authorization header contains base64 encoded client_id:client_secret
        call_args = mock_client.post.call_args
        auth_header = call_args[1]["headers"]["Authorization"]
        assert auth_header.startswith("Basic ")
    
    @patch('app.providers.embeddings.gigachat_embeddings.settings')
    async def test_get_token_caching(self, mock_settings):
        """Test that token is cached and not requested again"""
        mock_settings.GIGACHAT_CREDENTIALS = "test_credentials"
        mock_settings.GIGACHAT_CLIENT_ID = ""
        mock_settings.GIGACHAT_CLIENT_SECRET = ""
        mock_settings.GIGACHAT_SCOPE = "GIGACHAT_API_PERS"
        
        embeddings = GigaChatEmbeddings()
        embeddings._access_token = "cached_token"
        
        # Should return cached token without making HTTP request
        token = await embeddings._get_token()
        
        assert token == "cached_token"
    
    @patch('app.providers.embeddings.gigachat_embeddings.settings')
    async def test_get_token_http_error(self, mock_settings):
        """Test token retrieval with HTTP error"""
        mock_settings.GIGACHAT_CREDENTIALS = "test_credentials"
        mock_settings.GIGACHAT_CLIENT_ID = ""
        mock_settings.GIGACHAT_CLIENT_SECRET = ""
        mock_settings.GIGACHAT_SCOPE = "GIGACHAT_API_PERS"
        
        embeddings = GigaChatEmbeddings()
        
        # Mock httpx client with error
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=Mock(), response=Mock()
        )
        
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await embeddings._get_token()


@pytest.mark.asyncio
class TestGigaChatEmbeddingsEmbedQuery:
    """Tests for embed_query method"""
    
    @patch('app.providers.embeddings.gigachat_embeddings.settings')
    async def test_embed_query_single_text(self, mock_settings):
        """Test embedding a single query text"""
        mock_settings.GIGACHAT_CREDENTIALS = "test_credentials"
        mock_settings.GIGACHAT_CLIENT_ID = ""
        mock_settings.GIGACHAT_CLIENT_SECRET = ""
        mock_settings.GIGACHAT_SCOPE = "GIGACHAT_API_PERS"
        
        embeddings = GigaChatEmbeddings()
        embeddings._access_token = "test_token"
        
        # Mock embed_documents to return a list with one embedding
        with patch.object(embeddings, 'embed_documents', new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [[0.1, 0.2, 0.3]]
            
            result = await embeddings.embed_query("test query")
        
        assert result == [0.1, 0.2, 0.3]
        mock_embed.assert_called_once_with(["test query"], None)
    
    @patch('app.providers.embeddings.gigachat_embeddings.settings')
    async def test_embed_query_with_instruction(self, mock_settings):
        """Test embedding query with instruction"""
        mock_settings.GIGACHAT_CREDENTIALS = "test_credentials"
        mock_settings.GIGACHAT_CLIENT_ID = ""
        mock_settings.GIGACHAT_CLIENT_SECRET = ""
        mock_settings.GIGACHAT_SCOPE = "GIGACHAT_API_PERS"
        
        embeddings = GigaChatEmbeddings()
        embeddings._access_token = "test_token"
        
        with patch.object(embeddings, 'embed_documents', new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [[0.5, 0.6, 0.7]]
            
            result = await embeddings.embed_query("test query", instruction="search query")
        
        assert result == [0.5, 0.6, 0.7]
        mock_embed.assert_called_once_with(["test query"], "search query")


@pytest.mark.asyncio
class TestGigaChatEmbeddingsEmbedDocuments:
    """Tests for embed_documents method"""
    
    @patch('app.providers.embeddings.gigachat_embeddings.settings')
    async def test_embed_documents_multiple_texts(self, mock_settings):
        """Test embedding multiple documents"""
        mock_settings.GIGACHAT_CREDENTIALS = "test_credentials"
        mock_settings.GIGACHAT_CLIENT_ID = ""
        mock_settings.GIGACHAT_CLIENT_SECRET = ""
        mock_settings.GIGACHAT_SCOPE = "GIGACHAT_API_PERS"
        
        embeddings = GigaChatEmbeddings()
        embeddings._access_token = "test_token"
        
        # Mock httpx client
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.1, 0.2, 0.3]},
                {"embedding": [0.4, 0.5, 0.6]}
            ]
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            result = await embeddings.embed_documents(["text1", "text2"])
        
        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.4, 0.5, 0.6]
        
        # Verify request payload
        call_args = mock_client.post.call_args
        assert call_args[1]["json"]["model"] == "Embeddings"
        assert call_args[1]["json"]["input"] == ["text1", "text2"]
    
    @patch('app.providers.embeddings.gigachat_embeddings.settings')
    async def test_embed_documents_with_token_fetch(self, mock_settings):
        """Test embedding documents when token needs to be fetched"""
        mock_settings.GIGACHAT_CREDENTIALS = "test_credentials"
        mock_settings.GIGACHAT_CLIENT_ID = ""
        mock_settings.GIGACHAT_CLIENT_SECRET = ""
        mock_settings.GIGACHAT_SCOPE = "GIGACHAT_API_PERS"
        
        embeddings = GigaChatEmbeddings()
        
        # Mock _get_token
        with patch.object(embeddings, '_get_token', new_callable=AsyncMock) as mock_get_token:
            mock_get_token.return_value = "fetched_token"
            
            # Mock httpx client
            mock_response = Mock()
            mock_response.json.return_value = {
                "data": [{"embedding": [0.1, 0.2]}]
            }
            mock_response.raise_for_status = Mock()
            
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            
            with patch('httpx.AsyncClient', return_value=mock_client):
                result = await embeddings.embed_documents(["test"])
            
            mock_get_token.assert_called_once()
            assert result == [[0.1, 0.2]]
    
    @patch('app.providers.embeddings.gigachat_embeddings.settings')
    async def test_embed_documents_http_error(self, mock_settings):
        """Test embedding documents with HTTP error"""
        mock_settings.GIGACHAT_CREDENTIALS = "test_credentials"
        mock_settings.GIGACHAT_CLIENT_ID = ""
        mock_settings.GIGACHAT_CLIENT_SECRET = ""
        mock_settings.GIGACHAT_SCOPE = "GIGACHAT_API_PERS"
        
        embeddings = GigaChatEmbeddings()
        embeddings._access_token = "test_token"
        
        # Mock httpx client with error
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Server Error", request=Mock(), response=Mock()
        )
        
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await embeddings.embed_documents(["test"])
    
    @patch('app.providers.embeddings.gigachat_embeddings.settings')
    async def test_embed_documents_ssl_verification_enabled(self, mock_settings):
        """Test that SSL verification is enabled"""
        mock_settings.GIGACHAT_CREDENTIALS = "test_credentials"
        mock_settings.GIGACHAT_CLIENT_ID = ""
        mock_settings.GIGACHAT_CLIENT_SECRET = ""
        mock_settings.GIGACHAT_SCOPE = "GIGACHAT_API_PERS"
        
        embeddings = GigaChatEmbeddings()
        embeddings._access_token = "test_token"
        
        # Mock httpx client
        mock_response = Mock()
        mock_response.json.return_value = {"data": [{"embedding": [0.1]}]}
        mock_response.raise_for_status = Mock()
        
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch('httpx.AsyncClient') as mock_async_client:
            mock_async_client.return_value = mock_client
            
            await embeddings.embed_documents(["test"])
            
            # Verify AsyncClient was called with verify=True
            mock_async_client.assert_called_with(verify=True)
