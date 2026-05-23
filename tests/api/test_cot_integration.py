import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.api.chat import send_message_sync, send_message_stream
from app.models.message import Message

class TestCoTIntegration(unittest.TestCase):
    def setUp(self):
        self.mock_session_manager = AsyncMock()
        self.mock_rag_chain = AsyncMock()
        self.session_id = "session123"
        self.user_id = "user123"

    def test_send_message_sync_cot(self):
        async def run_test():
            request = MagicMock()
            request.content = "Complex question"
            request.role = "user"
            
            self.mock_session_manager.validate_session.return_value = True
            self.mock_session_manager.get_session.return_value = MagicMock(user_id=self.user_id)
            self.mock_session_manager.save_message.return_value = Message(role="assistant", content="Reasoned answer")
            
            # Mock RAGChain response
            async def mock_stream_gen():
                yield MagicMock(content="Reasoned", is_final=False)
                yield MagicMock(content=" answer", is_final=True)
            
            state = {"reasoning_steps": [{"step_number": 1, "thought": "Thinking..."}]}
            self.mock_rag_chain.process_user_message.return_value = (mock_stream_gen(), state)
            
            result = await send_message_sync(
                self.session_id, 
                request, 
                x_session_id=self.session_id, 
                session_manager=self.mock_session_manager,
                rag_chain=self.mock_rag_chain
            )
            
            self.assertEqual(result.assistant_response, "Reasoned answer")
            self.mock_rag_chain.process_user_message.assert_called_with(
                session_id=self.session_id,
                user_question="Complex question",
                user_id=self.user_id
            )

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
