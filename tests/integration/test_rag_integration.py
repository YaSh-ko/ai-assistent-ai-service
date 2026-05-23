import pytest
from datetime import date
from app.chains.rag_chain import RAGChain, RAGState
from app.data_access.repositories.dal import DataAccessLayer
from app.services.embedding_service import EmbeddingService

@pytest.fixture
def rag_chain(db_pool, chroma_client):
    """Create RAGChain with mocked dependencies"""
    from unittest.mock import AsyncMock, MagicMock
    from app.data_access.postgresql.session_repository import SessionRepository
    from app.data_access.postgresql.entry_repository import EntryRepository
    from app.data_access.postgresql.entry_thread_repository import EntryThreadRepository
    from app.data_access.postgresql.goal_thread_repository import GoalThreadRepository
    from app.data_access.postgresql.experiment_thread_repository import ExperimentThreadRepository
    from app.data_access.postgresql.analysis_thread_repository import AnalysisThreadRepository
    from app.data_access.postgresql.chat_session_repository import ChatSessionRepository
    from app.data_access.repositories.embedding_repository import EmbeddingRepository

    # Wrap pool in a mock provider with proper async methods
    mock_provider = MagicMock()
    mock_provider._ensure_connection = AsyncMock()
    pool = MagicMock()
    pool.fetchrow = AsyncMock(
        side_effect=db_pool.acquire.return_value.__aenter__.return_value.fetchrow.side_effect
    )
    pool.fetch = AsyncMock(
        side_effect=db_pool.acquire.return_value.__aenter__.return_value.fetch.side_effect
    )
    pool.execute = AsyncMock(
        side_effect=db_pool.acquire.return_value.__aenter__.return_value.execute.side_effect
    )
    pool.acquire = db_pool.acquire
    mock_provider.pool = pool

    dal = DataAccessLayer(
        session_repo=SessionRepository(mock_provider),
        chat_session_repo=ChatSessionRepository(mock_provider),
        entry_repo=EntryRepository(mock_provider),
        entry_thread_repo=EntryThreadRepository(mock_provider),
        goal_thread_repo=GoalThreadRepository(mock_provider),
        experiment_thread_repo=ExperimentThreadRepository(mock_provider),
        analysis_thread_repo=AnalysisThreadRepository(mock_provider),
        embedding_repo=EmbeddingRepository(chroma_client)
    )
    
    embedding_service = MagicMock()
    embedding_service.process_text = AsyncMock()
    embedding_service._embeddings_provider = MagicMock()
    embedding_service._embeddings_provider.embed_query = AsyncMock(return_value=[0.1] * 1024)
    embedding_service.generate_embedding = AsyncMock(return_value=[0.1] * 1024)
    
    mock_search_provider = MagicMock()
    mock_search_provider.search = AsyncMock(return_value=[])
    
    return RAGChain(dal=dal, embedding_service=embedding_service, hybrid_search_provider=mock_search_provider)

@pytest.mark.asyncio
async def test_rag_save_to_db(rag_chain, db_pool, chroma_client):
    """Проверка сохранения результатов RAG"""
    
    # Начальное состояние
    initial_state = RAGState(
        question="Я встретился с инвестором 25 ноября",
        user_id="user_123",
        thread_id="thread_456",
        session_id="session_789",
        context="",
        answer="",
        extracted_events=[{
            "title": "Встреча с инвестором",
            "description": "Встреча состоялась",
            "event_date": date(2025, 11, 25)
        }]
    )
    
    # Выполняем узел save_to_db
    result_state = await rag_chain.save_to_db(initial_state)
    
    # Проверяем что состояние вернулось
    assert result_state is not None
    
    # Проверяем PostgreSQL - entry should have been created
    # The mock will return entry_id_1
    pg_entry = await rag_chain.dal.entry_repo.get_by_id("entry_id_1")
    assert pg_entry is not None
    assert pg_entry['title'] == "Встреча с инвестором"
    
    # Проверяем ChromaDB
    embedding_count = await rag_chain.dal.embedding_repo.count_by_user("user_123")
    assert embedding_count > 0

@pytest.mark.asyncio
async def test_rag_full_chain(rag_chain):
    """Проверка полной RAG-цепочки"""
    
    initial_state = RAGState(
        question="Я встретился с инвестором",
        user_id="user_123",
        thread_id="thread_456",
        session_id="session_789",
        context="",
        answer="",
        extracted_events=[]
    )
    
    # Запускаем всю цепочку
    graph = rag_chain.build_graph()
    result = await graph.ainvoke(initial_state)
    
    # Проверяем что результат есть
    assert result is not None
    
    # Проверяем что все поля присутствуют
    assert 'question' in result
    assert 'answer' in result
    assert 'user_id' in result
