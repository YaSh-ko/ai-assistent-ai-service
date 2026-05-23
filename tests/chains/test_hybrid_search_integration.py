import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.chains.rag_chain import RAGChain

class TestHybridSearchIntegration(unittest.TestCase):
    def setUp(self):
        self.mock_dal = MagicMock()
        self.mock_embedding_service = AsyncMock()
        self.mock_llm_service = MagicMock()
        self.mock_reasoning_service = MagicMock()
        self.mock_hybrid_provider = AsyncMock()
        
        self.rag_chain = RAGChain(
            dal=self.mock_dal,
            embedding_service=self.mock_embedding_service,
            llm_service=self.mock_llm_service,
            reasoning_service=self.mock_reasoning_service,
            hybrid_search_provider=self.mock_hybrid_provider
        )

    def test_retrieve_events_uses_hybrid_search(self):
        async def run_test():
            state = {
                "question": "test query",
                "user_id": "user123",
                "query_embedding": [0.1, 0.2]
            }
            
            # Mock embedding generation
            self.mock_embedding_service.generate_embedding.return_value = [0.1, 0.2]
            
            # Mock search results
            expected_results = [{"id": 1, "score": 0.9}]
            self.mock_hybrid_provider.search.return_value = expected_results
            
            # Run retrieve_events
            new_state = await self.rag_chain.retrieve_events(state)
            
            # Verify hybrid provider was called
            self.mock_hybrid_provider.search.assert_called_once_with(
                query="test query",
                query_embedding=[0.1, 0.2],
                top_k=10,
                user_id="user123"
            )
            
            self.assertEqual(new_state["search_results"], expected_results)

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
