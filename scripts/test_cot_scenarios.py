import sys
import os
import asyncio
import logging
from datetime import date, datetime
from typing import List, Dict, Any
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

# Mock dependencies before imports
sys.modules["pydantic"] = MagicMock()
sys.modules["pydantic_settings"] = MagicMock()
sys.modules["asyncpg"] = MagicMock()
sys.modules["neo4j"] = MagicMock()
sys.modules["aiohttp"] = MagicMock()
sys.modules["gigachat"] = MagicMock()
sys.modules["langgraph"] = MagicMock()
sys.modules["langgraph.graph"] = MagicMock()
sys.modules["langgraph.graph"].StateGraph = MagicMock()
sys.modules["langgraph.graph"].END = "END"
sys.modules["langchain"] = MagicMock()
sys.modules["langchain.text_splitter"] = MagicMock()

# Mock settings
mock_settings = MagicMock()
mock_settings.REASONING_CONFIG = {
    "default_engine": "cot",
    "cot": {
        "max_reasoning_depth": 3,
        "max_clarifying_questions": 2,
        "enable_verification": True,
        "neo4j_max_depth": 2,
        "timeout_per_step": 5
    },
    "task_mapping": {
        "simple_question": "cot",
        "complex": "cot"
    }
}
sys.modules["app.core.config"] = MagicMock()
sys.modules["app.core.config"].settings = mock_settings

# Define Mock Classes
class MockQueryContext:
    def __init__(self, thread_id=None, user_id=None):
        self.thread_id = thread_id
        self.user_id = user_id

sys.modules["app.models.complexity_models"] = MagicMock()
sys.modules["app.models.complexity_models"].QueryContext = MockQueryContext

# Import classes to test (after mocking)
# We need to import RAGChain and ReasoningService, but we might need to patch them heavily
# or just mock the components they use.
# Let's try to use the real RAGChain logic but with mocked services.

from app.chains.rag_chain import RAGChain, RAGState

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Mock Data ---

MOCK_DIARY_ENTRIES = [
    {"id": 1, "title": "Ссора с женой", "description": "Опять поругались из-за уборки. Я устал на работе, а она начала пилить.", "event_date": date(2024, 3, 10), "metadata": {"category": "conflict", "emotion": "anger"}},
    {"id": 2, "title": "Проект сдан", "description": "Наконец-то закрыл сложный проект. Чувствую облегчение.", "event_date": date(2024, 3, 15), "metadata": {"category": "achievement", "emotion": "joy"}},
    {"id": 3, "title": "Разговор с женой", "description": "Поговорили спокойно. Решили нанять клининг.", "event_date": date(2024, 3, 12), "metadata": {"category": "reflection", "emotion": "calm"}},
    {"id": 4, "title": "Критика от босса", "description": "Босс раскритиковал мой отчет. Было обидно, но по делу.", "event_date": date(2024, 1, 20), "metadata": {"category": "work", "emotion": "sadness"}},
    {"id": 5, "title": "Еще критика", "description": "Снова замечания по коду. Я начинаю сомневаться в себе.", "event_date": date(2024, 2, 15), "metadata": {"category": "work", "emotion": "anxiety"}},
    {"id": 6, "title": "Успех на митинге", "description": "Презентация прошла отлично. Босс похвалил.", "event_date": date(2024, 4, 5), "metadata": {"category": "work", "emotion": "pride"}},
]

MOCK_GRAPH_CONNECTIONS = {
    1: [{"node": {"id": 3, "label": "Event"}, "relationship": "RESOLVED_BY"}],
    4: [{"node": {"id": 5, "label": "Event"}, "relationship": "FOLLOWED_BY"}],
}

# --- Mock Services ---

def setup_mocks():
    # DAL
    mock_dal = MagicMock()
    mock_dal.embedding_repo = MagicMock()
    mock_dal.embedding_repo.search_similar = AsyncMock()
    
    # Embedding Service
    mock_embedding_service = MagicMock()
    mock_embedding_service.generate_embedding = AsyncMock(return_value=[0.1]*1024)
    
    # LLM Service
    mock_llm_service = MagicMock()
    mock_llm_service.generate_response = AsyncMock()
    mock_llm_service.generate_response.return_value = MagicMock(content="Mocked LLM Response")
    
    # Reasoning Service
    mock_reasoning_service = MagicMock()
    mock_reasoning_service.execute_reasoning = AsyncMock()
    
    # Graph Repo
    mock_graph_repo = MagicMock()
    mock_graph_repo.find_related_nodes = AsyncMock()
    
    # Hybrid Search
    mock_hybrid_search = MagicMock()
    mock_hybrid_search.search = AsyncMock()
    
    # Reranker
    mock_reranker = MagicMock()
    mock_reranker.rerank = AsyncMock()

    return {
        "dal": mock_dal,
        "embedding_service": mock_embedding_service,
        "llm_service": mock_llm_service,
        "reasoning_service": mock_reasoning_service,
        "graph_repository": mock_graph_repo,
        "hybrid_search_provider": mock_hybrid_search,
        "reranker_provider": mock_reranker
    }

# --- Scenarios ---

async def run_scenario(name: str, question: str, expected_complexity: str, mocks: Dict[str, Any]):
    logger.info(f"\n--- Running Scenario: {name} ---")
    logger.info(f"Question: {question}")
    
    # Setup Chain
    chain = RAGChain(
        dal=mocks["dal"],
        embedding_service=mocks["embedding_service"],
        llm_service=mocks["llm_service"],
        reasoning_service=mocks["reasoning_service"],
        hybrid_search_provider=mocks["hybrid_search_provider"],
        reranker_provider=mocks["reranker_provider"],
        graph_repository=mocks["graph_repository"]
    )
    
    # Mock Complexity Classifier behavior for this scenario
    mock_classifier = MagicMock()
    mock_classifier.classify.return_value = MagicMock(
        level=MagicMock(value=expected_complexity), 
        suggested_model="gigachat_pro" if expected_complexity == "medium" else "gigachat_max",
        confidence=0.95
    )
    chain.complexity_classifier = mock_classifier

    # Mock Search Results based on keywords
    search_results = []
    for entry in MOCK_DIARY_ENTRIES:
        if any(word in entry["description"].lower() or word in entry["title"].lower() for word in question.lower().split()):
            search_results.append(entry)
    
    mocks["hybrid_search_provider"].search.return_value = search_results
    mocks["reranker_provider"].rerank.return_value = search_results[:3]

    # Mock Reasoning Service behavior
    if expected_complexity != "simple":
        mocks["reasoning_service"].execute_reasoning.return_value = {
            "steps": [
                {"step": "understand", "description": "Understanding intent"},
                {"step": "plan", "description": "Planning analysis"},
                {"step": "execute", "description": "Executing queries"},
                {"step": "verify", "description": "Verifying results"}
            ],
            "metadata": {"type": "cot", "duration": 1.5}
        }
    
    # Run Chain (simulate graph execution manually since we mocked langgraph)
    # 1. Classify
    state = {"question": question, "user_id": "test_user"}
    state = await chain.classify_query(state)
    assert state["complexity"] == expected_complexity
    logger.info(f"Complexity classified as: {state['complexity']}")
    
    # 2. Retrieve
    state = await chain.retrieve_events(state)
    logger.info(f"Retrieved {len(state['search_results'])} events")
    
    # 3. Filter
    state = await chain.filter_relevant(state)
    logger.info(f"Filtered to {len(state['filtered_results'])} events")
    
    # 4. Routing & Reasoning
    route = chain._route_based_on_complexity(state)
    logger.info(f"Route: {route}")
    
    if route == "complex":
        state = await chain.cot_reasoning(state)
        logger.info(f"CoT executed. Steps: {len(state.get('reasoning_steps', []))}")
        assert len(state.get("reasoning_steps", [])) > 0
    else:
        logger.info("CoT skipped (Simple route)")
        assert not state.get("reasoning_steps")
        
    # 5. Generate
    state = await chain.generate_response(state)
    logger.info(f"Response generated: {state['answer']}")
    
    logger.info(f"Scenario {name} PASSED")

async def main():
    mocks = setup_mocks()
    
    # Test 1: Simple Task
    await run_scenario(
        name="Simple Task",
        question="Что я записывал в дневник в марте?",
        expected_complexity="simple",
        mocks=mocks
    )
    
    # Test 2: Medium Task
    await run_scenario(
        name="Medium Task",
        question="Почему я часто попадаю в конфликты с партнером?",
        expected_complexity="complex", # Assuming medium maps to complex route or we adjust logic
        mocks=mocks
    )
    
    # Test 3: Complex Task
    await run_scenario(
        name="Complex Task",
        question="Как мои реакции на критику изменились за последний год?",
        expected_complexity="complex",
        mocks=mocks
    )
    
    # Edge Case 1: Empty Context
    logger.info("\n--- Running Scenario: Edge Case (Empty) ---")
    mocks["hybrid_search_provider"].search.return_value = []
    mocks["reranker_provider"].rerank.return_value = []
    await run_scenario(
        name="Empty Context",
        question="Расскажи о моих путешествиях",
        expected_complexity="simple", # Or complex, but result is empty
        mocks=mocks
    )

if __name__ == "__main__":
    asyncio.run(main())
