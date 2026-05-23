import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.services.session_manager import SessionManager
from app.models.chat_session import ChatSession, SessionStatus
from app.api.deps import get_session_manager, get_rag_chain
from app.models.message import Message

# Mock SessionManager
mock_session_manager = AsyncMock(spec=SessionManager)
# Mock RAGChain
mock_rag_chain = AsyncMock()

async def override_get_session_manager():
    yield mock_session_manager

async def override_get_rag_chain():
    yield mock_rag_chain

app.dependency_overrides[get_session_manager] = override_get_session_manager
app.dependency_overrides[get_rag_chain] = override_get_rag_chain

client = TestClient(app)

def test_create_session():
    user_id = "user123"
    session_id = "session123"
    
    mock_session = ChatSession(
        session_id=session_id,
        user_id=user_id,
        created_at="2023-01-01T00:00:00",
        updated_at="2023-01-01T00:00:00"
    )
    mock_session_manager.create_session.return_value = mock_session
    
    response = client.post("/api/v1/chat/sessions", json={"user_id": user_id})
    
    assert response.status_code == 200
    assert response.json()["session_id"] == session_id
    mock_session_manager.create_session.assert_called_with(user_id)

def test_send_message_sync():
    session_id = "session123"
    content = "Hello"
    
    mock_session_manager.validate_session.return_value = True
    mock_session_manager.save_message.return_value = Message(role="assistant", content="Hi there")
    mock_session_manager.get_session.return_value = MagicMock(user_id="user123")
    
    # Mock RAGChain response
    async def mock_stream_gen():
        yield MagicMock(content="Hi", is_final=False)
        yield MagicMock(content=" there", is_final=True)
    
    state = {"reasoning_steps": [], "filtered_results": []}
    mock_rag_chain.process_user_message.return_value = (mock_stream_gen(), state)

    response = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages", 
        json={"content": content},
        headers={"X-Session-ID": session_id}
    )
    
    assert response.status_code == 200
    assert response.json()["assistant_response"] == "Hi there"
    mock_session_manager.validate_session.assert_called_with(session_id)

def test_send_message_sync_mismatch_header():
    session_id = "session123"
    content = "Hello"
    
    mock_session_manager.validate_session.return_value = True
    mock_session_manager.save_message.return_value = Message(role="assistant", content="Hi there")
    mock_session_manager.get_session.return_value = MagicMock(user_id="user123")
    
    # Mock RAGChain response
    async def mock_stream_gen():
        yield MagicMock(content="Hi", is_final=False)
    
    state = {"reasoning_steps": [], "filtered_results": []}
    mock_rag_chain.process_user_message.return_value = (mock_stream_gen(), state)

    # Should still work but log warning
    response = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages", 
        json={"content": content},
        headers={"X-Session-ID": "other_session"}
    )
    
    assert response.status_code == 200

def test_get_history():
    session_id = "session123"
    mock_session_manager.get_history.return_value = [
        Message(role="user", content="Hi"),
        Message(role="assistant", content="Hello")
    ]
    
    response = client.get(f"/api/v1/chat/sessions/{session_id}/messages")
    
    assert response.status_code == 200
    assert len(response.json()) == 2
