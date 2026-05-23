import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.api.chat import send_message_sync, create_session, get_session, get_history, send_message_stream
from app.models.chat_session import ChatSession, SessionStatus
from app.models.message import Message

class TestChatAPI(unittest.TestCase):
    def setUp(self):
        self.mock_session_manager = AsyncMock()
        self.mock_rag_chain = AsyncMock()
        self.session_id = "session123"
        self.user_id = "user123"

    def test_create_session(self):
        async def run_test():
            request = MagicMock()
            request.user_id = self.user_id
            
            expected_session = ChatSession(
                session_id=self.session_id,
                user_id=self.user_id,
                created_at="2023-01-01T00:00:00",
                updated_at="2023-01-01T00:00:00"
            )
            self.mock_session_manager.create_session.return_value = expected_session
            
            result = await create_session(request, self.mock_session_manager)
            self.assertEqual(result, expected_session)
            self.mock_session_manager.create_session.assert_called_with(self.user_id)

        asyncio.run(run_test())

    def test_send_message_sync(self):
        async def run_test():
            request = MagicMock()
            request.content = "Hello"
            request.role = "user"
            request.model_name = "gpt-4"
            
            self.mock_session_manager.validate_session.return_value = True
            self.mock_session_manager.get_session.return_value = MagicMock(user_id=self.user_id)
            self.mock_session_manager.save_message.return_value = Message(role="assistant", content="Hi there")
            
            # Mock RAGChain response
            async def mock_stream_gen():
                yield MagicMock(content="Hi", is_final=False)
                yield MagicMock(content=" there", is_final=True)
            
            state = {"reasoning_steps": [], "filtered_results": []}
            self.mock_rag_chain.process_user_message.return_value = (mock_stream_gen(), state)
            
            result = await send_message_sync(
                self.session_id, 
                request, 
                x_session_id=self.session_id, 
                session_manager=self.mock_session_manager,
                rag_chain=self.mock_rag_chain
            )
            
            self.assertEqual(result.assistant_response, "Hi there")
            self.mock_session_manager.validate_session.assert_called_with(self.session_id)
            self.mock_session_manager.save_message.assert_any_call(self.session_id, "user", "Hello")
            self.mock_session_manager.save_message.assert_any_call(self.session_id, "assistant", "Hi there")

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
