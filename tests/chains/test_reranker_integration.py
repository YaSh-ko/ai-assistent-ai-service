import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.chains.rag_chain import RAGChain

class TestRerankerIntegration(unittest.TestCase):
    def setUp(self):
        self.mock_dal = MagicMock()
        self.mock_embedding_service = AsyncMock()
        self.mock_llm_service = MagicMock()
        self.mock_reasoning_service = MagicMock()
        self.mock_hybrid_provider = AsyncMock()
        self.mock_reranker_provider = AsyncMock()
        
        self.rag_chain = RAGChain(
            dal=self.mock_dal,
            embedding_service=self.mock_embedding_service,
            llm_service=self.mock_llm_service,
            reasoning_service=self.mock_reasoning_service,
            hybrid_search_provider=self.mock_hybrid_provider,
            reranker_provider=self.mock_reranker_provider
        )

    def test_filter_relevant_uses_reranker(self):
        async def run_test():
            search_results = [
                {"id": 1, "content": "doc1"},
                {"id": 2, "content": "doc2"},
                {"id": 3, "content": "doc3"}
            ]
            state = {
                "question": "test query",
                "search_results": search_results
            }
            
            # Mock reranker results
            filtered_results = [
                {"id": 1, "content": "doc1", "rerank_score": 9},
                {"id": 3, "content": "doc3", "rerank_score": 8}
            ]
            self.mock_reranker_provider.rerank.return_value = filtered_results
            
            # Run filter_relevant
            new_state = await self.rag_chain.filter_relevant(state)
            
            # Verify reranker was called
            self.mock_reranker_provider.rerank.assert_called_once_with(
                query="test query",
                documents=search_results,
                top_k=5
            )
            
            self.assertEqual(new_state["filtered_results"], filtered_results)
            self.assertIn("Запись 1 (релевантность: 0.00)", new_state["context"]) # Score 0 because mock didn't have final_score/score

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
