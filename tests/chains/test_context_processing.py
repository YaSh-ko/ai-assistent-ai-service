import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Mock langgraph
from unittest.mock import MagicMock
sys.modules["langgraph"] = MagicMock()
sys.modules["langgraph.graph"] = MagicMock()
sys.modules["langgraph.graph"].StateGraph = MagicMock()
sys.modules["langgraph.graph"].END = "END"
sys.modules["asyncpg"] = MagicMock()
sys.modules["langchain_gigachat"] = MagicMock()
sys.modules["langchain_chroma"] = MagicMock()
sys.modules["chromadb"] = MagicMock()
sys.modules["neo4j"] = MagicMock()

from app.chains.rag_chain import RAGChain
from app.services.pii_service import PIIService

class TestContextProcessing(unittest.TestCase):
    def setUp(self):
        self.mock_dal = MagicMock()
        self.mock_dal.chat_session_repo = AsyncMock()
        self.mock_embedding_service = AsyncMock()
        self.mock_llm_service = AsyncMock()
        self.mock_reasoning_service = MagicMock()
        self.mock_hybrid_provider = AsyncMock()
        self.mock_reranker_provider = AsyncMock()
        self.mock_graph_repository = AsyncMock()
        self.pii_service = PIIService()
        
        self.rag_chain = RAGChain(
            dal=self.mock_dal,
            embedding_service=self.mock_embedding_service,
            llm_service=self.mock_llm_service,
            reasoning_service=self.mock_reasoning_service,
            hybrid_search_provider=self.mock_hybrid_provider,
            reranker_provider=self.mock_reranker_provider,
            graph_repository=self.mock_graph_repository,
            pii_service=self.pii_service
        )

    def test_history_inclusion_and_sanitization(self):
        async def run_test():
            state = {
                "question": "my email is test@example.com",
                "complexity": "simple",
                "session_id": "sess_123",
                "answer": "Contact me at 555-0199",
                "extracted_events": [{"title": "Meeting with john@example.com"}]
            }
            
            # Mock history
            self.mock_dal.chat_session_repo.get_history.return_value = [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"}
            ]
            
            # Mock LLM response
            mock_response = MagicMock()
            mock_response.content = "Response"
            self.mock_llm_service.generate_response.return_value = mock_response
            
            # 1. Test generate_response includes history
            await self.rag_chain.generate_response(state)
            
            self.mock_dal.chat_session_repo.get_history.assert_called_with("sess_123", limit=5)
            call_args = self.mock_llm_service.generate_response.call_args[1]
            self.assertIn("ИСТОРИЯ ДИАЛОГА", call_args["prompt"])
            self.assertIn("User: Hi", call_args["prompt"])
            
            # 2. Test save_to_db sanitizes data
            self.mock_dal.save_entry_with_embedding = AsyncMock()
            
            await self.rag_chain.save_to_db(state)
            
            # Check event sanitization
            self.mock_dal.save_entry_with_embedding.assert_called()
            call_args_save = self.mock_dal.save_entry_with_embedding.call_args[1]
            self.assertEqual(call_args_save["title"], "Meeting with [EMAIL]")
            
            # Check answer sanitization (not directly saved in save_to_db logic shown, but good to check if we were saving it)
            # The current save_to_db saves entries. Let's verify it uses pii_service.
            # We can check if pii_service methods were called.
            # But here we used real PIIService, so we check the result passed to save_entry_with_embedding.

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
