"""
Tests for SessionManager.
Coverage target: 80%+
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
from app.chat.session_manager import SessionManager, ISessionManager
from app.models.chat_session import ChatSession, SessionStatus
from app.models.message import Message


@pytest.fixture
def mock_repository():
    """Mock ChatSessionRepository."""
    repo = MagicMock()
    return repo


@pytest.fixture
def session_manager(mock_repository):
    """Create SessionManager instance."""
    return SessionManager(mock_repository)


@pytest.fixture
def sample_session_data():
    """Sample session data."""
    now = datetime.now()
    return {
        'thread_id': 'session123',
        'user_id': 'user456',
        'status': SessionStatus.ACTIVE.value,
        'history': [],
        'context': {},
        'metadata': {},
        'states': [],
        'created_at': now,
        'last_active_at': now,
    }


class TestCreateSession:
    """Test session creation."""
    
    @pytest.mark.asyncio
    async def test_create_session_success(self, session_manager, mock_repository, sample_session_data):
        """Test successful session creation."""
        mock_repository.create = AsyncMock(return_value=sample_session_data)
        
        with patch('uuid.uuid4', return_value='session123'):
            session = await session_manager.create_session('user456')
            
            assert isinstance(session, ChatSession)
            assert session.session_id == 'session123'
            assert session.user_id == 'user456'
            assert session.status == SessionStatus.ACTIVE
            
            # Verify session is cached
            assert 'session123' in session_manager._cache
    
    @pytest.mark.asyncio
    async def test_create_session_db_failure(self, session_manager, mock_repository):
        """Test session creation when database fails."""
        mock_repository.create = AsyncMock(return_value=None)
        
        with pytest.raises(RuntimeError, match="Failed to create session"):
            await session_manager.create_session('user456')


class TestGetSession:
    """Test getting sessions."""
    
    @pytest.mark.asyncio
    async def test_get_session_from_cache(self, session_manager, sample_session_data):
        """Test getting session from cache."""
        session = ChatSession(**sample_session_data)
        session_manager._cache['session123'] = session
        
        result = await session_manager.get_session('session123')
        
        assert result is session
        assert result.session_id == 'session123'
    
    @pytest.mark.asyncio
    async def test_get_session_from_db(self, session_manager, mock_repository, sample_session_data):
        """Test getting session from database."""
        mock_repository.get_by_id = AsyncMock(return_value=sample_session_data)
        
        result = await session_manager.get_session('session123')
        
        assert result is not None
        assert result.session_id == 'session123'
        
        # Verify session is cached
        assert 'session123' in session_manager._cache
    
    @pytest.mark.asyncio
    async def test_get_session_not_found(self, session_manager, mock_repository):
        """Test getting non-existent session."""
        mock_repository.get_by_id = AsyncMock(return_value=None)
        
        result = await session_manager.get_session('nonexistent')
        
        assert result is None


class TestUpdateSession:
    """Test session updates."""
    
    @pytest.mark.asyncio
    async def test_update_session_success(self, session_manager, mock_repository, sample_session_data):
        """Test successful session update."""
        updated_data = sample_session_data.copy()
        updated_data['status'] = SessionStatus.CLOSED.value
        
        mock_repository.update = AsyncMock(return_value=updated_data)
        
        result = await session_manager.update_session('session123', {'status': SessionStatus.CLOSED.value})
        
        assert result is not None
        assert result.status == SessionStatus.CLOSED
        
        # Verify cache is updated
        assert 'session123' in session_manager._cache
        assert session_manager._cache['session123'].status == SessionStatus.CLOSED
    
    @pytest.mark.asyncio
    async def test_update_session_not_found(self, session_manager, mock_repository):
        """Test updating non-existent session."""
        mock_repository.update = AsyncMock(return_value=None)
        
        result = await session_manager.update_session('nonexistent', {'status': 'closed'})
        
        assert result is None


class TestSaveMessage:
    """Test saving messages."""
    
    @pytest.mark.asyncio
    async def test_save_message_success(self, session_manager, mock_repository, sample_session_data):
        """Test successful message save."""
        updated_data = sample_session_data.copy()
        updated_data['history'] = [{'role': 'user', 'content': 'Hello'}]
        
        mock_repository.add_message = AsyncMock(return_value=updated_data)
        
        # Add session to cache
        session = ChatSession(**sample_session_data)
        session_manager._cache['session123'] = session
        
        message = await session_manager.save_message('session123', 'user', 'Hello')
        
        assert isinstance(message, Message)
        assert message.role == 'user'
        assert message.content == 'Hello'
    
    @pytest.mark.asyncio
    async def test_save_message_session_not_cached(self, session_manager, mock_repository, sample_session_data):
        """Test saving message when session not in cache."""
        updated_data = sample_session_data.copy()
        updated_data['history'] = [{'role': 'assistant', 'content': 'Hi'}]
        
        mock_repository.add_message = AsyncMock(return_value=updated_data)
        
        message = await session_manager.save_message('session123', 'assistant', 'Hi')
        
        assert isinstance(message, Message)
        assert message.role == 'assistant'


class TestGetHistory:
    """Test getting message history."""
    
    @pytest.mark.asyncio
    async def test_get_history_success(self, session_manager, mock_repository):
        """Test successful history retrieval."""
        history_data = [
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi there'}
        ]
        
        mock_repository.get_history = AsyncMock(return_value=history_data)
        
        history = await session_manager.get_history('session123', limit=10)
        
        assert len(history) == 2
        assert all(isinstance(msg, Message) for msg in history)
        assert history[0].role == 'user'
        assert history[1].role == 'assistant'
    
    @pytest.mark.asyncio
    async def test_get_history_with_pagination(self, session_manager, mock_repository):
        """Test history retrieval with pagination."""
        history_data = [
            {'role': 'user', 'content': f'Message {i}'}
            for i in range(5)
        ]
        
        mock_repository.get_history = AsyncMock(return_value=history_data)
        
        history = await session_manager.get_history('session123', limit=5, offset=10)
        
        assert len(history) == 5
        mock_repository.get_history.assert_called_once_with('session123', 5, 10)
    
    @pytest.mark.asyncio
    async def test_get_history_empty(self, session_manager, mock_repository):
        """Test getting empty history."""
        mock_repository.get_history = AsyncMock(return_value=[])
        
        history = await session_manager.get_history('session123')
        
        assert history == []


class TestCloseSession:
    """Test closing sessions."""
    
    @pytest.mark.asyncio
    async def test_close_session_success(self, session_manager, mock_repository, sample_session_data):
        """Test successful session closure."""
        updated_data = sample_session_data.copy()
        updated_data['metadata'] = {'status': SessionStatus.CLOSED.value}
        updated_data['status'] = SessionStatus.CLOSED.value
        
        mock_repository.update = AsyncMock(return_value=updated_data)
        
        # Add session to cache
        session = ChatSession(**sample_session_data)
        session_manager._cache['session123'] = session
        
        result = await session_manager.close_session('session123')
        
        assert result is True
        
        # Verify session removed from cache
        assert 'session123' not in session_manager._cache
    
    @pytest.mark.asyncio
    async def test_close_session_not_found(self, session_manager, mock_repository):
        """Test closing non-existent session."""
        mock_repository.get_by_id = AsyncMock(return_value=None)
        mock_repository.update = AsyncMock(return_value=None)
        
        result = await session_manager.close_session('nonexistent')
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_close_session_not_in_cache(self, session_manager, mock_repository, sample_session_data):
        """Test closing session that's not in cache."""
        updated_data = sample_session_data.copy()
        updated_data['metadata'] = {'status': SessionStatus.CLOSED.value}
        updated_data['status'] = SessionStatus.CLOSED.value
        
        mock_repository.get_by_id = AsyncMock(return_value=sample_session_data)
        mock_repository.update = AsyncMock(return_value=updated_data)
        
        result = await session_manager.close_session('session123')
        
        assert result is True


class TestValidateSession:
    """Test session validation."""
    
    @pytest.mark.asyncio
    async def test_validate_session_active(self, session_manager, mock_repository, sample_session_data):
        """Test validating active session."""
        mock_repository.get_by_id = AsyncMock(return_value=sample_session_data)
        
        result = await session_manager.validate_session('session123')
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_session_closed(self, session_manager, mock_repository, sample_session_data):
        """Test validating closed session."""
        closed_data = sample_session_data.copy()
        closed_data.pop('status', None)
        closed_data['metadata'] = {'status': SessionStatus.CLOSED.value}
        
        mock_repository.get_by_id = AsyncMock(return_value=closed_data)
        
        result = await session_manager.validate_session('session123')
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_session_not_found(self, session_manager, mock_repository):
        """Test validating non-existent session."""
        mock_repository.get_by_id = AsyncMock(return_value=None)
        
        result = await session_manager.validate_session('nonexistent')
        
        assert result is False


class TestCacheSession:
    """Test session caching."""
    
    def test_cache_session(self, session_manager, sample_session_data):
        """Test caching a session."""
        session = ChatSession(**sample_session_data)
        
        session_manager._cache_session(session)
        
        assert 'session123' in session_manager._cache
        assert session_manager._cache['session123'] is session


class TestCacheTTL:
    """Test cache TTL configuration."""
    
    def test_cache_ttl_default(self, session_manager):
        """Test default cache TTL."""
        assert session_manager._cache_ttl == timedelta(minutes=30)
