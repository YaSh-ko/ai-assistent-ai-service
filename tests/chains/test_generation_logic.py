import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.chains.rag_chain import RAGChain
from app.core.model_selector import ModelSelector

class TestGenerationLogic(unittest.TestCase):
    def setUp(self):
        self.mock_dal = MagicMock()
        self.mock_embedding_service = AsyncMock()
        self.mock_llm_service = AsyncMock()
        self.mock_reasoning_service = MagicMock()
        self.mock_hybrid_provider = AsyncMock()
        self.mock_reranker_provider = AsyncMock()
        self.mock_graph_repository = AsyncMock()
        
        self.rag_chain = RAGChain(
            dal=self.mock_dal,
            embedding_service=self.mock_embedding_service,
            llm_service=self.mock_llm_service,
            reasoning_service=self.mock_reasoning_service,
            hybrid_search_provider=self.mock_hybrid_provider,
            reranker_provider=self.mock_reranker_provider,
            graph_repository=self.mock_graph_repository
        )

    def test_generate_response_uses_model_selector(self):
        async def run_test():
            state = {
                "question": "complex question",
                "complexity": "complex",
                "context": "some context",
                "reasoning_steps": [{"step_number": 1, "description": "step 1"}]
            }
            
            # Mock LLM response
            mock_response = MagicMock()
            mock_response.content = "Deleuze answer"
            self.mock_llm_service.generate_response.return_value = mock_response
            
            # Run generate_response
            new_state = await self.rag_chain.generate_response(state)
            
            # Verify ModelSelector usage (implicitly via arguments passed to generate_response)
            # Complex -> gigachat_max (internal name), temperature 0.7
            self.mock_llm_service.generate_response.assert_called_once()
            call_args = self.mock_llm_service.generate_response.call_args[1]
            
            self.assertEqual(call_args["model_name"], "gigachat_max")
            self.assertEqual(call_args["temperature"], 0.7)
            self.assertIn("Gilles Deleuze", call_args["system_prompt"])
            self.assertIn("RAG КОНТЕКСТ", call_args["prompt"])
            
            self.assertEqual(new_state["answer"], "Deleuze answer")

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
