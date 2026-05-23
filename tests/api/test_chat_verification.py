import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os
import json
from datetime import datetime
import uuid

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Mock dependencies
sys.modules["langgraph"] = MagicMock()
sys.modules["langgraph.graph"] = MagicMock()
sys.modules["langgraph.graph"].StateGraph = MagicMock()
sys.modules["langgraph.graph"].END = "END"
sys.modules["asyncpg"] = MagicMock()
sys.modules["langchain_gigachat"] = MagicMock()
sys.modules["langchain_chroma"] = MagicMock()
sys.modules["chromadb"] = MagicMock()
sys.modules["neo4j"] = MagicMock()
sys.modules["neo4j.exceptions"] = MagicMock()

from fastapi.testclient import TestClient
from fastapi import FastAPI, Depends, Header
from app.api.v1.chat_controller import router, create_session, send_message_sync, send_message_stream, get_history, close_session
from app.models.chat_session import ChatSession, SessionStatus
from app.models.message import Message
from app.models.response import ChatResponse
from app.services.session_manager import SessionManager
from app.chains.rag_chain import RAGChain

# Setup FastAPI app for testing
app = FastAPI()
app.include_router(router)

class TestChatVerification(unittest.TestCase):
    def setUp(self):
        self.mock_session_manager = AsyncMock(spec=SessionManager)
        self.mock_rag_chain = AsyncMock(spec=RAGChain)
        
        # Override dependencies
        app.dependency_overrides[SessionManager] = lambda: self.mock_session_manager
        app.dependency_overrides[RAGChain] = lambda: self.mock_rag_chain
        
        # Need to override the specific dependency functions used in router
        from app.api.deps import get_session_manager, get_rag_chain
        app.dependency_overrides[get_session_manager] = lambda: self.mock_session_manager
        app.dependency_overrides[get_rag_chain] = lambda: self.mock_rag_chain
        
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides = {}

    def test_create_session(self):
        """Test Session Creation & Validation"""
        session_id = str(uuid.uuid4())
        self.mock_session_manager.create_session.return_value = ChatSession(
            session_id=session_id,
            user_id="user_123",
            status=SessionStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        response = self.client.post("/chat/sessions", json={"user_id": "user_123"})
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["session_id"], session_id)
        self.assertEqual(data["user_id"], "user_123")
        self.assertEqual(data["status"], "active")

    def test_message_persistence_and_response(self):
        """Test Message Persistence & Response"""
        session_id = "sess_123"
        self.mock_session_manager.validate_session.return_value = True
        self.mock_session_manager.get_session.return_value = MagicMock(user_id="user_1")
        
        # Mock RAG Chain response
        mock_state = {
            "processing_time_ms": 100,
            "complexity": "simple",
            "selected_model": "test-model",
            "reasoning_steps": [],
            "reasoning_metadata": {"confidence": 0.9, "total_time_ms": 50},
            "filtered_results": [],
            "graph_insights": []
        }
        
        async def mock_stream():
            yield MagicMock(content="Hello")
            yield MagicMock(content=" World")
            
        self.mock_rag_chain.process_user_message.return_value = (mock_stream(), mock_state)
        
        response = self.client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"content": "Hi", "role": "user"}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["assistant_response"], "Hello World")
        
        # Verify persistence calls
        self.assertEqual(self.mock_session_manager.save_message.call_count, 2)
        # First call: User message
        self.mock_session_manager.save_message.assert_any_call(session_id, "user", "Hi")
        # Second call: Assistant message
        self.mock_session_manager.save_message.assert_any_call(session_id, "assistant", "Hello World")

    def test_streaming_sse(self):
        """Test Streaming (SSE)"""
        session_id = "sess_stream"
        self.mock_session_manager.validate_session.return_value = True
        self.mock_session_manager.get_session.return_value = MagicMock(user_id="user_1")
        
        mock_state = {"reasoning_steps": [{"step_number": 1, "description": "Thinking"}]}
        
        async def mock_stream():
            yield MagicMock(content="Chunk1", is_final=False)
            yield MagicMock(content="Chunk2", is_final=True)
            
        self.mock_rag_chain.process_user_message.return_value = (mock_stream(), mock_state)
        
        with self.client.stream("POST", f"/chat/sessions/{session_id}/stream", json={"content": "Stream me"}) as response:
            self.assertEqual(response.status_code, 200)
            chunks = list(response.iter_lines())
            
            # Filter empty lines
            chunks = [line for line in chunks if line]
            
            # Verify chunk types
            # 1. Processing
            self.assertIn('type": "processing"', chunks[0])
            # 2. Reasoning
            self.assertIn('type": "reasoning_step"', chunks[1])
            # 3. Text chunks
            text_chunks = [c for c in chunks if 'type": "text"' in c]
            self.assertGreaterEqual(len(text_chunks), 2, "Text chunks should be 2 or more")
            # 4. Done
            self.assertIn('type": "done"', chunks[-2])
            self.assertEqual(chunks[-1], "data: [DONE]")

    def test_context_switching(self):
        """Test Context Switching (X-Session-ID)"""
        # This test verifies that the header is validated against the path param
        session_id = "sess_A"
        self.mock_session_manager.validate_session.return_value = True
        self.mock_session_manager.get_session.return_value = MagicMock(user_id="user_1")
        
        # Mock RAG Chain
        self.mock_rag_chain.process_user_message.return_value = (AsyncMock(), {})
        
        # Case 1: Matching ID
        response = self.client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"content": "test"},
            headers={"X-Session-ID": session_id}
        )
        self.assertEqual(response.status_code, 200)
        
        # Case 2: Mismatch ID (Should log warning but proceed if path ID is valid)
        # In our implementation we just log warning, so it should still succeed if path ID is valid
        response = self.client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"content": "test"},
            headers={"X-Session-ID": "sess_B"}
        )
        self.assertEqual(response.status_code, 200)
        
        # Case 3: Invalid Session (Path)
        self.mock_session_manager.validate_session.return_value = False
        response = self.client.post(
            f"/chat/sessions/invalid_sess/messages",
            json={"content": "test"}
        )
        self.assertEqual(response.status_code, 404)

    def test_history_pagination(self):
        """Test History Pagination"""
        session_id = "sess_hist"
        
        # Mock history return
        self.mock_session_manager.get_history.return_value = [
            Message(role="user", content=f"msg {i}") for i in range(5)
        ]
        
        # Test default
        response = self.client.get(f"/chat/sessions/{session_id}/messages")
        self.assertEqual(response.status_code, 200)
        self.mock_session_manager.get_history.assert_called_with(session_id, 50, 0)
        
        # Test with params
        response = self.client.get(f"/chat/sessions/{session_id}/messages?limit=10&offset=5")
        self.assertEqual(response.status_code, 200)
        self.mock_session_manager.get_history.assert_called_with(session_id, 10, 5)

    def test_session_closure(self):
        """Test Session Closure"""
        session_id = "sess_close"
        
        # 1. Close session
        self.mock_session_manager.close_session.return_value = True
        response = self.client.post(f"/chat/sessions/{session_id}/close")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "closed")
        
        # 2. Try to send message to closed session
        self.mock_session_manager.validate_session.return_value = False # Simulate closed
        response = self.client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"content": "test"}
        )
        self.assertEqual(response.status_code, 404)

    def test_error_handling(self):
        """Test Error Handling (Reasoning)"""
        session_id = "sess_err"
        self.mock_session_manager.validate_session.return_value = True
        
        # Mock Exception in RAG Chain
        self.mock_rag_chain.process_user_message.side_effect = Exception("Reasoning Engine Failure")
        
        response = self.client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"content": "crash me"}
        )
        
        self.assertEqual(response.status_code, 500)
        self.assertIn("Reasoning Engine Failure", response.json()["detail"])

    def test_metrics(self):
        """Test Metrics"""
        session_id = "sess_metrics"
        self.mock_session_manager.validate_session.return_value = True
        self.mock_session_manager.get_session.return_value = MagicMock(user_id="user_1")
        
        mock_state = {
            "processing_time_ms": 1234,
            "reasoning_metadata": {"total_time_ms": 567}
        }
        self.mock_rag_chain.process_user_message.return_value = (AsyncMock(), mock_state)
        
        response = self.client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"content": "test"}
        )
        
        data = response.json()
        self.assertEqual(data["metadata"]["session_duration_ms"], 1234)
        self.assertEqual(data["reasoning"]["total_time_ms"], 567)

    def test_frontend_integration_structure(self):
        """
        Test: agent-chat-ui корректно отображает ответы и историю из API
        
        This test strictly validates that the API response structure matches 
        exactly what the agent-chat-ui expects for rendering.
        """
        session_id = "sess_ui_test"
        self.mock_session_manager.validate_session.return_value = True
        self.mock_session_manager.get_session.return_value = MagicMock(user_id="u1")
        
        # 1. Validate History Structure (for Chat History display)
        # UI expects: id, role, content, timestamp
        msg_id = str(uuid.uuid4())
        now = datetime.now()
        self.mock_session_manager.get_history.return_value = [
            Message(id=msg_id, role="user", content="Hi", timestamp=now)
        ]
        
        resp_hist = self.client.get(f"/chat/sessions/{session_id}/messages")
        self.assertEqual(resp_hist.status_code, 200)
        hist_data = resp_hist.json()
        self.assertIsInstance(hist_data, list)
        self.assertGreater(len(hist_data), 0, "History should not be empty")
        msg = hist_data[0]
        self.assertIn("id", msg)
        self.assertIn("role", msg)
        self.assertIn("content", msg)
        self.assertIn("timestamp", msg)
        
        # 2. Validate ChatResponse Structure (for Reasoning/Sources display)
        # UI expects: assistant_response, reasoning (steps), sources (rag_events)
        mock_state = {
            "processing_time_ms": 100,
            "complexity": "simple",
            "selected_model": "test-model",
            "reasoning_steps": [
                {
                    "step_number": 1,
                    "description": "Step 1",
                    "thought": "Thinking",
                    "observation": "Observed",
                    "time_ms": 10
                }
            ],
            "reasoning_metadata": {"confidence": 1.0, "total_time_ms": 10},
            "filtered_results": [
                {"id": "doc1", "title": "Title", "summary": "Summary", "event_date": "2023-01-01"}
            ],
            "graph_insights": []
        }
        self.mock_rag_chain.process_user_message.return_value = (AsyncMock(), mock_state)
        
        resp_msg = self.client.post(
            f"/chat/sessions/{session_id}/messages",
            json={"content": "test"}
        )
        self.assertEqual(resp_msg.status_code, 200)
        data = resp_msg.json()
        
        # Check Reasoning fields for UI
        self.assertIn("reasoning", data)
        self.assertIn("steps", data["reasoning"])
        step = data["reasoning"]["steps"][0]
        self.assertIn("step_number", step)
        self.assertIn("description", step) # UI uses this for accordion title
        self.assertIn("thought", step)     # UI uses this for content
        
        # Check Source fields for UI
        self.assertIn("sources", data)
        self.assertIn("rag_events", data["sources"])
        event = data["sources"]["rag_events"][0]
        self.assertIn("title", event)      # UI displays title
        self.assertIn("summary", event)    # UI displays summary
        
        # Check Metadata
        self.assertIn("metadata", data)
        self.assertIn("model_used", data["metadata"]) # UI might show model badge

    def test_e2e_scenario(self):
        """Test E2E Scenario"""
        # 1. Create Session
        session_id = "sess_e2e"
        self.mock_session_manager.create_session.return_value = ChatSession(
            session_id=session_id, user_id="u1", status=SessionStatus.ACTIVE,
            created_at=datetime.now(), updated_at=datetime.now()
        )
        
        # 2. Send Message
        self.mock_session_manager.validate_session.return_value = True
        self.mock_session_manager.get_session.return_value = MagicMock(user_id="u1")
        self.mock_rag_chain.process_user_message.return_value = (AsyncMock(), {})
        
        resp1 = self.client.post(f"/chat/sessions/{session_id}/messages", json={"content": "Q1"})
        self.assertEqual(resp1.status_code, 200)
        
        # 3. Stream Message
        with self.client.stream("POST", f"/chat/sessions/{session_id}/stream", json={"content": "Q2"}) as resp2:
            self.assertEqual(resp2.status_code, 200)
            
        # 4. Get History
        self.client.get(f"/chat/sessions/{session_id}/messages")
        self.mock_session_manager.get_history.assert_called()
        
        # 5. Close
        self.mock_session_manager.close_session.return_value = True
        resp3 = self.client.post(f"/chat/sessions/{session_id}/close")
        self.assertEqual(resp3.status_code, 200)


if __name__ == "__main__":
    unittest.main()
