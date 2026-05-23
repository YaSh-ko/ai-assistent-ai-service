import pytest
from unittest.mock import MagicMock, AsyncMock
from app.chains.rag_chain import RAGChain

@pytest.fixture
def mock_dependencies():
    return {
        "dal": MagicMock(),
        "embedding_service": MagicMock(),
        "llm_service": MagicMock(),
        "reasoning_service": MagicMock(),
        "hybrid_search": MagicMock(),
        "reranker": MagicMock(),
        "graph_repo": MagicMock()
    }

@pytest.fixture
def rag_chain(mock_dependencies):
    chain = RAGChain(
        dal=mock_dependencies["dal"],
        embedding_service=mock_dependencies["embedding_service"],
        llm_service=mock_dependencies["llm_service"],
        reasoning_service=mock_dependencies["reasoning_service"],
        hybrid_search_provider=mock_dependencies["hybrid_search"],
        reranker_provider=mock_dependencies["reranker"],
        graph_repository=mock_dependencies["graph_repo"]
    )
    return chain

def test_complexity_routing(rag_chain):
    # Test Simple
    simple_state = {"complexity": "simple"}
    assert rag_chain._route_based_on_complexity(simple_state) == "simple"
    
    # Test Complex
    complex_state = {"complexity": "complex"}
    assert rag_chain._route_based_on_complexity(complex_state) == "complex"

@pytest.mark.asyncio
async def test_cot_reasoning_node(rag_chain, mock_dependencies):
    state = {
        "question": "Test",
        "user_id": "u1",
        "filtered_results": [],
        "complexity": "complex",
        "thread_id": "t1"
    }
    
    mock_dependencies["reasoning_service"].execute_reasoning = AsyncMock(return_value={
        "steps": [{"step": 1}],
        "metadata": {"type": "cot"}
    })
    
    new_state = await rag_chain.cot_reasoning(state)
    
    assert len(new_state["reasoning_steps"]) == 1
    assert new_state["reasoning_engine_used"] == "cot"
