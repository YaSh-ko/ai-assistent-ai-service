"""
Tests for ChatSessionRepository.
Coverage target: 80%+
"""

import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from app.data_access.postgresql.chat_session_repository import ChatSessionRepository
from app.models.chat_session import SessionStatus


@pytest.fixture
def mock_pool():
    """Mock database pool."""
    pool = MagicMock()
    return pool


@pytest.fixture
def repository(mock_pool):
    """Create repository instance."""
    repo = ChatSessionRepository(mock_pool)
    return repo


class TestParseJsonFields:
    """Test JSON field parsing."""
    
    def test_parse_json_fields_with_strings(self, repository):
        """Test parsing JSON string fields."""
        row = {
            'session_id': 'test123',
            'history': '[]',
            'context': '{}',
            'metadata': '{"key": "value"}'
        }
        
        result = repository._parse_json_fields(row)
        
        assert result['history'] == []
        assert result['context'] == {}
        assert result['metadata'] == {"key": "value"}
    
    def test_parse_json_fields_with_dicts(self, repository):
        """Test parsing when fields are already dicts."""
        row = {
            'session_id': 'test123',
            'history': [],
            'context': {},
            'metadata': {"key": "value"}
        }
        
        result = repository._parse_json_fields(row)
        
        assert result['history'] == []
        assert result['context'] == {}
        assert result['metadata'] == {"key": "value"}
    
    def test_parse_json_fields_with_invalid_json(self, repository):
        """Test parsing with invalid JSON strings."""
        row = {
            'session_id': 'test123',
            'history': 'invalid json',
            'context': '{}',
            'metadata': '{}'
        }
        
        result = repository._parse_json_fields(row)
        
        # Should keep original value if parsing fails
        assert result['history'] == 'invalid json'
    
    def test_parse_json_fields_none_row(self, repository):
        """Test parsing None row."""
        result = repository._parse_json_fields(None)
        
        assert result is None


class TestCreate:
    """Test session creation."""
    
    @pytest.mark.asyncio
    async def test_create_success(self, repository):
        """Test successful session creation."""
        mock_row = {
            'session_id': 'session123',
            'user_id': 'user456',
            'status': 'active',
            'history': '[]',
            'context': '{}',
            'metadata': '{}',
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        with patch.object(repository, 'fetch_one', new=AsyncMock(return_value=mock_row)):
            result = await repository.create('user456', 'session123')
            
            assert result is not None
            assert result['session_id'] == 'session123'
            assert result['user_id'] == 'user456'
            assert result['history'] == []
    
    @pytest.mark.asyncio
    async def test_create_returns_none(self, repository):
        """Test creation when database returns None."""
        with patch.object(repository, 'fetch_one', new=AsyncMock(return_value=None)):
            result = await repository.create('user456', 'session123')
            
            assert result is None


class TestGetById:
    """Test getting session by ID."""
    
    @pytest.mark.asyncio
    async def test_get_by_id_success(self, repository):
        """Test successful retrieval."""
        mock_row = {
            'session_id': 'session123',
            'user_id': 'user456',
            'history': '[]',
            'context': '{}',
            'metadata': '{}'
        }
        
        with patch.object(repository, 'fetch_one', new=AsyncMock(return_value=mock_row)):
            result = await repository.get_by_id('session123')
            
            assert result is not None
            assert result['session_id'] == 'session123'
    
    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repository):
        """Test retrieval when session not found."""
        with patch.object(repository, 'fetch_one', new=AsyncMock(return_value=None)):
            result = await repository.get_by_id('nonexistent')
            
            assert result is None


class TestUpdate:
    """Test session update."""
    
    @pytest.mark.asyncio
    async def test_update_simple_fields(self, repository):
        """Test updating simple fields."""
        mock_row = {
            'session_id': 'session123',
            'status': 'closed',
            'history': '[]',
            'context': '{}',
            'metadata': '{}'
        }
        
        with patch.object(repository, 'fetch_one', new=AsyncMock(return_value=mock_row)):
            result = await repository.update('session123', {'status': 'closed'})
            
            assert result is not None
            assert result['status'] == 'closed'
    
    @pytest.mark.asyncio
    async def test_update_json_fields(self, repository):
        """Test updating JSON fields."""
        mock_row = {
            'session_id': 'session123',
            'context': '{"key": "value"}',
            'history': '[]',
            'metadata': '{}'
        }
        
        with patch.object(repository, 'fetch_one', new=AsyncMock(return_value=mock_row)):
            result = await repository.update('session123', {
                'context': {'key': 'value'},
                'metadata': {'updated': True}
            })
            
            assert result is not None
            assert result['context'] == {'key': 'value'}
    
    @pytest.mark.asyncio
    async def test_update_with_datetime(self, repository):
        """Test updating with datetime objects."""
        mock_row = {
            'session_id': 'session123',
            'metadata': '{"timestamp": "2025-01-01T00:00:00"}',
            'history': '[]',
            'context': '{}'
        }
        
        with patch.object(repository, 'fetch_one', new=AsyncMock(return_value=mock_row)):
            result = await repository.update('session123', {
                'metadata': {'timestamp': datetime(2025, 1, 1)}
            })
            
            assert result is not None


class TestDelete:
    """Test session deletion."""
    
    @pytest.mark.asyncio
    async def test_delete_success(self, repository):
        """Test successful deletion."""
        with patch.object(repository, 'execute', new=AsyncMock(return_value="DELETE 1")):
            result = await repository.delete('session123')
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_delete_not_found(self, repository):
        """Test deletion when session not found."""
        with patch.object(repository, 'execute', new=AsyncMock(return_value="DELETE 0")):
            result = await repository.delete('nonexistent')
            
            assert result is False


class TestAddMessage:
    """Test adding messages."""
    
    @pytest.mark.asyncio
    async def test_add_message_success(self, repository):
        """Test successful message addition."""
        mock_row = {
            'session_id': 'session123',
            'history': '[{"role": "user", "content": "Hello"}]',
            'context': '{}',
            'metadata': '{}'
        }
        
        message = {'role': 'user', 'content': 'Hello'}
        
        with patch.object(repository, 'fetch_one', new=AsyncMock(return_value=mock_row)):
            result = await repository.add_message('session123', message)
            
            assert result is not None
            assert len(result['history']) == 1
    
    @pytest.mark.asyncio
    async def test_add_message_with_datetime(self, repository):
        """Test adding message with datetime."""
        mock_row = {
            'session_id': 'session123',
            'history': '[]',
            'context': '{}',
            'metadata': '{}'
        }
        
        message = {
            'role': 'user',
            'content': 'Hello',
            'timestamp': datetime.now()
        }
        
        with patch.object(repository, 'fetch_one', new=AsyncMock(return_value=mock_row)):
            result = await repository.add_message('session123', message)
            
            assert result is not None


class TestGetHistory:
    """Test getting message history."""
    
    @pytest.mark.asyncio
    async def test_get_history_with_messages(self, repository):
        """Test getting history with messages."""
        messages = [
            {'role': 'user', 'content': f'Message {i}'}
            for i in range(30)
        ]
        
        mock_row = {
            'history': json.dumps(messages)
        }
        
        with patch.object(repository, 'fetch_one', new=AsyncMock(return_value=mock_row)):
            result = await repository.get_history('session123', limit=10)
            
            assert len(result) == 10
            # Should return most recent messages
            assert result[0]['content'] == 'Message 20'
    
    @pytest.mark.asyncio
    async def test_get_history_with_offset(self, repository):
        """Test getting history with offset."""
        messages = [
            {'role': 'user', 'content': f'Message {i}'}
            for i in range(30)
        ]
        
        mock_row = {
            'history': json.dumps(messages)
        }
        
        with patch.object(repository, 'fetch_one', new=AsyncMock(return_value=mock_row)):
            result = await repository.get_history('session123', limit=10, offset=5)
            
            assert len(result) == 10
            assert result[0]['content'] == 'Message 15'
    
    @pytest.mark.asyncio
    async def test_get_history_empty(self, repository):
        """Test getting history when empty."""
        mock_row = {
            'history': '[]'
        }
        
        with patch.object(repository, 'fetch_one', new=AsyncMock(return_value=mock_row)):
            result = await repository.get_history('session123')
            
            assert result == []
    
    @pytest.mark.asyncio
    async def test_get_history_session_not_found(self, repository):
        """Test getting history when session not found."""
        with patch.object(repository, 'fetch_one', new=AsyncMock(return_value=None)):
            result = await repository.get_history('nonexistent')
            
            assert result == []


class TestCleanupClosed:
    """Test cleanup of closed sessions."""
    
    @pytest.mark.asyncio
    async def test_cleanup_closed_success(self, repository):
        """Test successful cleanup."""
        with patch.object(repository, 'execute', new=AsyncMock(return_value="DELETE 5")):
            result = await repository.cleanup_closed(24)
            
            assert result == 5
    
    @pytest.mark.asyncio
    async def test_cleanup_closed_none_deleted(self, repository):
        """Test cleanup when no sessions deleted."""
        with patch.object(repository, 'execute', new=AsyncMock(return_value="DELETE 0")):
            result = await repository.cleanup_closed(24)
            
            assert result == 0
    
    @pytest.mark.asyncio
    async def test_cleanup_closed_invalid_response(self, repository):
        """Test cleanup with invalid response format."""
        with patch.object(repository, 'execute', new=AsyncMock(return_value="INVALID")):
            result = await repository.cleanup_closed(24)
            
            assert result == 0
