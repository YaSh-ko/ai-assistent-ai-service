import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

# Mock dependencies
sys.modules["pydantic"] = MagicMock()
sys.modules["pydantic_settings"] = MagicMock()

# Define a real class for QueryContext to avoid typing issues
class MockQueryContext:
    pass

sys.modules["app.models.complexity_models"] = MagicMock()
sys.modules["app.models.complexity_models"].QueryContext = MockQueryContext

mock_settings = MagicMock()
mock_settings.REASONING_CONFIG = {
    "default_engine": "cot",
    "task_mapping": {"complex": "cot"}
}
sys.modules["app.core.config"] = MagicMock()
sys.modules["app.core.config"].settings = mock_settings

# Mock database drivers
sys.modules["asyncpg"] = MagicMock()
sys.modules["neo4j"] = MagicMock()
sys.modules["aiohttp"] = MagicMock()
sys.modules["gigachat"] = MagicMock()

# Mock langgraph and langchain
sys.modules["langgraph"] = MagicMock()
sys.modules["langgraph.graph"] = MagicMock()
mock_state_graph = MagicMock()
mock_compiled_graph = MagicMock()
mock_compiled_graph.ainvoke = AsyncMock()
mock_compiled_graph.ainvoke.return_value = {
    "answer": "Final Answer",
    "complexity": "complex",
    "selected_model": "gigachat_pro",
    "reasoning_steps": [{"description": "Step 1"}],
    "filtered_results": []
}
mock_state_graph.return_value.compile.return_value = mock_compiled_graph
sys.modules["langgraph.graph"].StateGraph = mock_state_graph
sys.modules["langgraph.graph"].END = "END"
sys.modules["langchain"] = MagicMock()
sys.modules["langchain.text_splitter"] = MagicMock()

# Mock other services
mock_dal = MagicMock()
mock_embedding_service = MagicMock()
mock_llm_service = MagicMock()
mock_llm_service.generate_response = AsyncMock()
mock_llm_service.generate_response.return_value = MagicMock(content="Final Answer")

mock_reasoning_service = MagicMock()
mock_reasoning_service.execute_reasoning = AsyncMock()
mock_reasoning_service.execute_reasoning.return_value = {
    "steps": [{"step_number": 1, "description": "Step 1", "thought": "Thinking..."}],
    "metadata": {"type": "cot"}
}

# Mock Complexity Classifier
mock_classifier = MagicMock()
mock_classifier.classify.return_value = MagicMock(level=MagicMock(value="complex"), suggested_model="gigachat_pro", confidence=0.9)
sys.modules["app.core.complexity_classifier"] = MagicMock()
sys.modules["app.core.complexity_classifier"].get_complexity_classifier.return_value = mock_classifier

from app.chains.rag_chain import RAGChain

async def main():
    print("Testing RAGChain Integration...")
    
    chain = RAGChain(
        dal=mock_dal,
        embedding_service=mock_embedding_service,
        llm_service=mock_llm_service,
        reasoning_service=mock_reasoning_service
    )
    
    # Test 1: Conditional Routing
    print("\nTest 1: Routing")
    simple_state = {"complexity": "simple"}
    route = chain._route_based_on_complexity(simple_state)
    assert route == "simple"
    print("Simple routing verified")
    
    complex_state = {"complexity": "complex"}
    route = chain._route_based_on_complexity(complex_state)
    assert route == "complex"
    print("Complex routing verified")

    # Test 2: CoT Reasoning Node
    print("\nTest 2: CoT Reasoning Node")
    state = {
        "question": "Complex question",
        "user_id": "user1",
        "filtered_results": [],
        "complexity": "complex",
        "thread_id": "thread1"
    }
    
    new_state = await chain.cot_reasoning(state)
    
    # Verify reasoning service called
    mock_reasoning_service.execute_reasoning.assert_called_once()
    args = mock_reasoning_service.execute_reasoning.call_args
    assert args.kwargs['question'] == "Complex question"
    assert args.kwargs['task_type'] == "complex"
    
    # Verify state update
    assert len(new_state['reasoning_steps']) == 1
    assert new_state['reasoning_engine_used'] == "cot"
    print("CoT Reasoning node verified")
    
    print("\nVerification successful!")

if __name__ == "__main__":
    asyncio.run(main())
