import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock
import sys
import os
from datetime import datetime

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

from app.api.chat import send_message_sync, SendMessageRequest
from app.models.response import ChatResponse

class TestChatResponse(unittest.TestCase):
    def test_structured_response(self):
        async def run_test():
            # Mock dependencies
            mock_session_manager = AsyncMock()
            mock_session_manager.validate_session.return_value = True
            mock_session_manager.get_session.return_value = MagicMock(user_id="user_1")
            mock_session_manager.save_message.return_value = MagicMock()
            
            mock_rag_chain = AsyncMock()
            
            # Mock process_user_message return
            mock_state = {
                "question": "test question",
                "complexity": "complex",
                "selected_model": "gigachat-pro",
                "processing_time_ms": 123.45,
                "reasoning_steps": [
                    {
                        "step_number": 1,
                        "description": "Step 1",
                        "thought": "Thinking...",
                        "observation": "Observed",
                        "time_ms": 10.0
                    }
                ],
                "reasoning_metadata": {"confidence": 0.9, "total_time_ms": 100.0},
                "filtered_results": [
                    {"id": "doc_1", "title": "Doc 1", "summary": "Summary 1"}
                ],
                "graph_insights": [{"insight": "test insight"}]
            }
            
            async def mock_stream():
                yield MagicMock(content="Hello")
                yield MagicMock(content=" World")
                
            mock_rag_chain.process_user_message.return_value = (mock_stream(), mock_state)
            
            # Call endpoint
            request = SendMessageRequest(content="test question")
            response = await send_message_sync(
                session_id="sess_1",
                request=request,
                session_manager=mock_session_manager,
                rag_chain=mock_rag_chain
            )
            
            # Verify response
            self.assertIsInstance(response, ChatResponse)
            self.assertEqual(response.session_id, "sess_1")
            self.assertEqual(response.user_message, "test question")
            self.assertEqual(response.assistant_response, "Hello World")
            
            # Verify Reasoning
            self.assertIsNotNone(response.reasoning)
            self.assertEqual(response.reasoning.type, "pattern_analysis")
            self.assertEqual(len(response.reasoning.steps), 1)
            self.assertEqual(response.reasoning.steps[0].description, "Step 1")
            self.assertEqual(response.reasoning.confidence_score, 0.9)
            
            # Verify Sources
            self.assertIsNotNone(response.sources)
            self.assertEqual(len(response.sources.rag_events), 1)
            self.assertEqual(response.sources.rag_events[0].id, "doc_1")
            self.assertIn("Neo4j", response.sources.data_sources)
            
            # Verify Metadata
            self.assertIsNotNone(response.metadata)
            self.assertEqual(response.metadata.model_used, "gigachat-pro")
            self.assertEqual(response.metadata.complexity, "complex")

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
