import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.session_manager import SessionManager
from app.models.chat_session import ChatSession, SessionStatus
from app.models.message import Message

@pytest.fixture
def mock_repo():
    return AsyncMock()

@pytest.fixture
def session_manager(mock_repo):
    return SessionManager(mock_repo)

@pytest.mark.asyncio
async def test_create_session(session_manager, mock_repo):
    user_id = "user123"
    session_id = "session123"
    
    mock_repo.create.return_value = {
        "session_id": session_id,
        "user_id": user_id,
        "status": "active",
        "created_at": "2023-01-01T00:00:00",
        "updated_at": "2023-01-01T00:00:00",
        "history": [],
        "context": {},
        "metadata": {}
    }
    
    session = await session_manager.create_session(user_id)
    
    assert session.session_id == session_id
    assert session.user_id == user_id
    assert session.status == SessionStatus.ACTIVE
    
    # Check if cached
    assert session_id in session_manager._cache

@pytest.mark.asyncio
async def test_get_session_cache_hit(session_manager):
    session_id = "session123"
    session = ChatSession(
        session_id=session_id,
        user_id="user123",
        created_at="2023-01-01T00:00:00",
        updated_at="2023-01-01T00:00:00"
    )
    session_manager._cache[session_id] = session
    
    result = await session_manager.get_session(session_id)
    assert result == session
    session_manager.repository.get_by_id.assert_not_called()

@pytest.mark.asyncio
async def test_save_message(session_manager, mock_repo):
    session_id = "session123"
    role = "user"
    content = "hello"
    
    # Setup cache
    session = ChatSession(
        session_id=session_id,
        user_id="user123",
        created_at="2023-01-01T00:00:00",
        updated_at="2023-01-01T00:00:00"
    )
    session_manager._cache[session_id] = session
    
    message = await session_manager.save_message(session_id, role, content)
    
    assert message.role == role
    assert message.content == content
    
    mock_repo.add_message.assert_called_once()
    
    # Check if updated_at changed (mocked datetime would be better but simple check is enough)
    # assert session.updated_at > ... 
