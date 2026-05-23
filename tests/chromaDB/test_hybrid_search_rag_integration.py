import pytest
import uuid
import asyncio
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch, Mock

from app.chains.rag_chain import RAGChain, RAGState
from app.providers.search.bm25_provider import BM25Provider
from app.providers.search.vector_search_provider import VectorSearchProvider
from app.providers.search.hybrid_search_provider import HybridSearchProvider
from app.services.embedding_service import EmbeddingService
from app.data_access.repositories.dal import DataAccessLayer


class MockBM25Provider:
    """Mock BM25 provider for testing"""
    
    def __init__(self):
        self.search = AsyncMock()
    
    async def search(self, query, k=10, **kwargs):
        return [
            {
                "id": "bm25_doc1",
                "user_id": "test_user",
                "event_date": "2024-01-01",
                "title": "Тренировка в зале",
                "description": "Интенсивная тренировка с тяжелыми весами",
                "bm25_score": 2.5
            },
            {
                "id": "bm25_doc2",
                "user_id": "test_user",
                "event_date": "2024-01-02",
                "title": "Купил кроссовки",
                "description": "Новые кроссовки для бега",
                "bm25_score": 1.8
            }
        ]


class MockVectorSearchProvider:
    """Mock Vector search provider for testing"""
    
    def __init__(self):
        self.search = AsyncMock()
    
    async def search(self, query_embedding, top_k=10, **kwargs):
        return [
            {
                "id": "vector_doc1",
                "page_content": "Сегодня была интенсивная тренировка в зале с тяжелыми весами",
                "metadata": {
                    "user_id": "test_user",
                    "entry_id": "doc1",
                    "title": "Тренировка в зале",
                    "event_date": "2024-01-01"
                },
                "score": 0.85
            },
            {
                "id": "vector_doc2",
                "page_content": "Купил новые кроссовки для бега и тренировок",
                "metadata": {
                    "user_id": "test_user",
                    "entry_id": "doc2",
                    "title": "Купил кроссовки",
                    "event_date": "2024-01-02"
                },
                "score": 0.75
            }
        ]


class MockEmbeddingService:
    """Mock embedding service for testing"""
    
    def __init__(self):
        self._embeddings_provider = MagicMock()
        self._embeddings_provider.embed_query = AsyncMock(return_value=[0.1] * 1024)

    async def generate_embedding(self, text: str):
        return await self._embeddings_provider.embed_query(text)


class MockDataAccessLayer:
    """Mock DAL for testing"""
    
    def __init__(self):
        self.session_repo = Mock()
        self.entry_repo = Mock()
        self.entry_thread_repo = Mock()
        self.goal_thread_repo = Mock()
        self.experiment_thread_repo = Mock()
        self.analysis_thread_repo = Mock()
        self.embedding_repo = Mock()
        
        self.save_entry_with_embedding = AsyncMock()

class MockLLMResponse:
    def __init__(self, content):
        self.content = content

class MockLLMService:
    """Mock LLM service for testing"""
    async def generate_response(self, prompt: str, **kwargs):
        return MockLLMResponse("Generated answer based on context")


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service fixture"""
    return MockEmbeddingService()


@pytest.fixture
def mock_dal():
    """Mock DAL fixture"""
    return MockDataAccessLayer()


@pytest.fixture
def mock_search_provider():
    """Mock hybrid search provider fixture"""
    bm25_mock = MockBM25Provider()
    vector_mock = MockVectorSearchProvider()
    
    # Create real HybridSearchProvider with mocks
    with patch('app.providers.search.hybrid_search_provider.settings') as mock_settings:
        mock_settings.SEARCH_CONFIG = {'bm25_weight': 0.5, 'vector_weight': 0.5}
        provider = HybridSearchProvider(bm25_mock, vector_mock)
    
    # Mock the search method to return test data
    provider.search = AsyncMock(return_value=[
        {
            'id': 'doc1',
            'user_id': 'test_user',
            'event_date': '2024-01-01',
            'title': 'Тренировка в зале',
            'description': 'Интенсивная тренировка с тяжелыми весами',
            'page_content': 'Сегодня была интенсивная тренировка в зале с тяжелыми весами',
            'metadata': {'entry_id': 'doc1', 'user_id': 'test_user'},
            'final_score': 0.9
        },
        {
            'id': 'doc2',
            'user_id': 'test_user',
            'event_date': '2024-01-02',
            'title': 'Купил кроссовки',
            'description': 'Новые кроссовки для бега',
            'page_content': 'Купил новые кроссовки для бега и тренировок',
            'metadata': {'entry_id': 'doc2', 'user_id': 'test_user'},
            'final_score': 0.8
        }
    ])
    
    return provider


@pytest.fixture
def rag_chain(mock_dal, mock_embedding_service, mock_search_provider):
    """RAG chain fixture with mocked dependencies"""
    return RAGChain(
        dal=mock_dal,
        embedding_service=mock_embedding_service,
        hybrid_search_provider=mock_search_provider,
        llm_service=MockLLMService()
    )


@pytest.mark.asyncio
async def test_hybrid_search_rag_integration(rag_chain, mock_search_provider, mock_embedding_service, mock_dal):
    """Тест 9: Интеграция с RAG цепочкой"""
    print("\n=== Тест 9: Интеграция RAG цепи с гибридным поиском ===")
    
    # 1. Запустить RAG цепочку с тестовым запросом
    test_question = "Какие у меня были тренировки?"
    user_id = "test_user_hybrid"
    session_id = "session_test_hybrid"
    
    print(f"1. Запуск RAG цепи с запросом: '{test_question}'")
    
    # Создаем начальное состояние
    initial_state = RAGState(
        question=test_question,
        context="",
        answer="",
        user_id=user_id,
        thread_id="thread_test_hybrid",
        session_id=session_id,
        extracted_events=[]
    )
    
    # 2. Узел retrieve_events получает данные через hybrid_search_provider
    print("2. Выполнение retrieve_events с гибридным поиском...")
    
    # Сбрасываем моки
    mock_search_provider.search.reset_mock()
    mock_embedding_service._embeddings_provider.embed_query.reset_mock()
    
    # Выполняем retrieve_events
    state_after_retrieve = await rag_chain.retrieve_events(initial_state)
    
    # Проверяем вызовы
    mock_embedding_service._embeddings_provider.embed_query.assert_called_once()
    mock_search_provider.search.assert_called_once()
    
    # Проверяем аргументы вызова search
    call_args = mock_search_provider.search.call_args
    assert call_args[1]["query"] == test_question
    assert call_args[1]["top_k"] == 10
    
    # Проверяем, что результаты поиска получены
    assert "search_results" in state_after_retrieve
    assert len(state_after_retrieve["search_results"]) > 0
    print(f"   Найдено {len(state_after_retrieve['search_results'])} событий")
    
    # Проверяем формат контекста - ЭТО ДЕЛАЕТСЯ ПОСЛЕ filter_relevant
    # assert "Date:" in state_after_retrieve["context"]
    # assert "Content:" in state_after_retrieve["context"]
    # assert "тренировка" in state_after_retrieve["context"].lower()
    
    # 3. Контекст передается в последующие узлы
    print("3. Передача контекста через цепочку узлов...")
    
    # Проходим через остальные узлы
    state_after_filter = await rag_chain.filter_relevant(state_after_retrieve)
    
    # Проверяем контекст после фильтрации
    assert state_after_filter["context"] != ""
    assert "Дата:" in state_after_filter["context"]
    
    state_after_reasoning = await rag_chain.cot_reasoning(state_after_filter)
    
    # Проверяем, что контекст сохранился
    assert state_after_reasoning["context"] == state_after_retrieve["context"]
    
    # 4. LLM генерирует ответ (в текущей реализации это заглушка)
    print("4. Генерация ответа...")
    state_after_generate = await rag_chain.generate_response(state_after_reasoning)
    
    assert "answer" in state_after_generate
    assert state_after_generate["answer"] != "", "Ответ не должен быть пустым"
    assert "Generated answer based on context" in state_after_generate["answer"]
    print(f"   Ответ сгенерирован: {state_after_generate['answer'][:100]}...")
    
    # 5. Узел save_to_db сохраняет результаты через репозитории
    print("5. Подготовка и сохранение извлеченных событий в БД...")
    
    # Создаем тестовые извлеченные события
    test_extracted_events = [
        {
            "title": "Новая тренировка",
            "description": "Дополнительная тренировка в спортзале",
            "event_date": date.today().isoformat()
        }
    ]
    
    state_after_generate["extracted_events"] = test_extracted_events
    
    # Сбрасываем моки для нового вызова
    mock_embedding_service._embeddings_provider.embed_query.reset_mock()
    mock_embedding_service._embeddings_provider.embed_query.return_value = [0.5] * 1024
    mock_dal.save_entry_with_embedding.reset_mock()
    
    # Вызываем save_to_db
    state_after_save = await rag_chain.save_to_db(state_after_generate)
    
    # 6. Проверяем, что данные сохраняются через репозитории
    print("6. Проверка вызовов сохранения в БД...")
    
    # Проверяем вызовы embed_query для каждого события
    # assert mock_embedding_service._embeddings_provider.embed_query.called
    
    # Проверяем вызов save_entry_with_embedding
    mock_dal.save_entry_with_embedding.assert_called_once()
    
    # Проверяем аргументы вызова
    call_args = mock_dal.save_entry_with_embedding.call_args
    assert call_args[1]["user_id"] == user_id
    assert "тренировка" in call_args[1]["title"].lower()
    assert isinstance(call_args[1]["event_date"], date)
    
    print(f"   Вызов сохранения в БД выполнен с аргументами:")
    print(f"     user_id: {call_args[1]['user_id']}")
    print(f"     title: {call_args[1]['title']}")
    print(f"     event_date: {call_args[1]['event_date']}")
    
    print("\n✅ Все проверки пройдены успешно!")
    print("=== Тест завершен ===")


@pytest.mark.asyncio
async def test_rag_chain_full_graph_execution(rag_chain, mock_search_provider, mock_embedding_service, mock_dal):
    """Тест полного выполнения графа RAG цепи"""
    print("\n=== Тест полного выполнения графа RAG цепи ===")
    
    # Сбрасываем все моки
    mock_search_provider.search.reset_mock()
    mock_embedding_service._embeddings_provider.embed_query.reset_mock()
    mock_dal.save_entry_with_embedding.reset_mock()
    
    # Настраиваем возвращаемые значения
    mock_embedding_service._embeddings_provider.embed_query.return_value = [0.3] * 1024
    mock_search_provider.search.return_value = [
        {
            'id': 'full_graph_doc',
            'user_id': 'test_user',
            'event_date': '2024-01-01',
            'title': 'Тренировка',
            'description': 'Тренировка в зале',
            'page_content': 'Интенсивная тренировка',
            'metadata': {'entry_id': 'doc1'},
            'final_score': 0.9
        }
    ]
    
    # Создаем граф
    workflow = rag_chain.build_graph()
    
    # Создаем начальное состояние
    initial_state = RAGState(
        question="Что я делал на тренировке?",
        context="",
        answer="",
        user_id="test_user",
        thread_id="thread_full_graph",
        session_id="session_full_graph",
        extracted_events=[]
    )
    
    print("Запуск полного графа...")
    
    # Запускаем граф
    final_state = await workflow.ainvoke(initial_state)
    
    # Проверяем результаты
    assert "context" in final_state
    assert final_state["context"] != ""
    assert "answer" in final_state
    assert final_state["answer"] != ""
    
    # Проверяем вызовы
    mock_embedding_service._embeddings_provider.embed_query.assert_called()
    mock_search_provider.search.assert_called_once()
    
    # Проверяем, что save_to_db не вызывался, так как extracted_events пуст
    mock_dal.save_entry_with_embedding.assert_not_called()
    
    print(f"   Контекст: {len(final_state['context'])} символов")
    print(f"   Ответ: {final_state['answer'][:100]}...")
    print("✅ Граф выполнен успешно!")


@pytest.mark.asyncio
async def test_hybrid_search_with_different_queries(rag_chain, mock_search_provider):
    """Тест гибридного поиска с разными запросами"""
    print("\n=== Тест гибридного поиска с разными запросами ===")
    
    test_cases = [
        {
            "query": "тренировка с весами",
            "description": "Семантический поиск тренировок"
        },
        {
            "query": "кроссовки для бега",
            "description": "Ключевой поиск покупок"
        },
        {
            "query": "отдых после активности",
            "description": "Комбинированный поиск"
        }
    ]
    
    for test_case in test_cases:
        print(f"\nЗапрос: '{test_case['query']}' ({test_case['description']})")
        
        # Сбрасываем мок
        mock_search_provider.search.reset_mock()
        
        # Выполняем retrieve_events
        state = RAGState(
            question=test_case["query"],
            context="",
            answer="",
            user_id="test_user",
            thread_id="thread_variations",
            session_id="session_variations",
            extracted_events=[]
        )
        
        state = await rag_chain.retrieve_events(state)
        state = await rag_chain.filter_relevant(state)
        
        # Проверяем вызов
        mock_search_provider.search.assert_called_once()
        
        # Проверяем аргументы
        call_args = mock_search_provider.search.call_args
        assert call_args[1]["query"] == test_case["query"]
        
        # Проверяем контекст
        assert state["context"] != ""
        print(f"   Длина контекста: {len(state['context'])} символов")
        print("   ✅ Успешно")


@pytest.mark.asyncio
async def test_save_to_db_with_multiple_events(rag_chain, mock_embedding_service, mock_dal):
    """Тест сохранения нескольких извлеченных событий в БД"""
    print("\n=== Тест сохранения нескольких событий в БД ===")
    
    # Создаем тестовые события
    extracted_events = [
        {
            "title": "Утренняя пробежка",
            "description": "Пробежал 5 км в парке",
            "event_date": "2024-01-15"
        },
        {
            "title": "Покупка спортивной формы",
            "description": "Купил новую спортивную форму для тренировок",
            "event_date": "2024-01-16"
        },
        {
            "title": "Вечерняя тренировка",
            "description": "Силовая тренировка в зале",
            "event_date": "2024-01-17"
        }
    ]
    
    # Создаем состояние
    state = RAGState(
        question="Какие спортивные активности у меня были?",
        context="Контекст с информацией о тренировках",
        answer="Ответ LLM",
        user_id="test_user",
        thread_id="thread_multiple_events",
        session_id="session_multiple_events",
        extracted_events=extracted_events
    )
    
    # Настраиваем моки
    mock_embedding_service._embeddings_provider.embed_query.reset_mock()
    mock_embedding_service._embeddings_provider.embed_query.side_effect = [
        [0.6] * 1024,  # Для первого события
        [0.7] * 1024,  # Для второго события
        [0.8] * 1024   # Для третьего события
    ]
    mock_dal.save_entry_with_embedding.reset_mock()
    
    print(f"Сохранение {len(extracted_events)} событий...")
    
    # Вызываем save_to_db
    await rag_chain.save_to_db(state)
    
    # Проверяем вызовы
    # assert mock_embedding_service._embeddings_provider.embed_query.call_count == len(extracted_events)
    assert mock_dal.save_entry_with_embedding.call_count == len(extracted_events)
    
    print(f"   Вызовов embed_query: {mock_embedding_service._embeddings_provider.embed_query.call_count}")
    print(f"   Вызовов сохранения: {mock_dal.save_entry_with_embedding.call_count}")
    
    # Проверяем аргументы последнего вызова
    call_args = mock_dal.save_entry_with_embedding.call_args_list[-1]
    assert "тренировка" in call_args[1]["title"].lower()
    
    print("   ✅ Все события обработаны успешно!")


@pytest.mark.asyncio
async def test_save_to_db_with_invalid_date(rag_chain, mock_embedding_service, mock_dal):
    """Тест сохранения событий с невалидной датой"""
    print("\n=== Тест сохранения событий с невалидной датой ===")
    
    # Создаем событие с невалидной датой
    extracted_events = [
        {
            "title": "Событие с невалидной датой",
            "description": "Описание события",
            "event_date": "невалидная-дата"
        }
    ]
    
    # Создаем состояние
    state = RAGState(
        question="Тестовый вопрос",
        context="Контекст",
        answer="Ответ",
        user_id="test_user",
        thread_id="thread_invalid_date",
        session_id="session_invalid_date",
        extracted_events=extracted_events
    )
    
    # Настраиваем моки
    mock_embedding_service._embeddings_provider.embed_query.reset_mock()
    mock_embedding_service._embeddings_provider.embed_query.return_value = [0.5] * 1024
    mock_dal.save_entry_with_embedding.reset_mock()
    
    print("Сохранение события с невалидной датой...")
    
    # Вызываем save_to_db (должен обработать ошибку и использовать текущую дату)
    await rag_chain.save_to_db(state)
    
    # Проверяем вызовы
    # mock_embedding_service._embeddings_provider.embed_query.assert_called_once()
    print(f"DEBUG: save_entry_with_embedding call count: {mock_dal.save_entry_with_embedding.call_count}")
    mock_dal.save_entry_with_embedding.assert_called_once()
    
    # Проверяем, что save_entry_with_embedding был вызван с текущей датой или строкой
    call_args = mock_dal.save_entry_with_embedding.call_args
    assert isinstance(call_args[1]["event_date"], (date, str))
    
    print("   ✅ Событие сохранено с обработкой невалидной даты")


if __name__ == "__main__":
    # Для отладки
    import asyncio
    import sys
    import os
    
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    async def run_tests():
        print("Запустите тесты через pytest:")
        print("  pytest python-ai-service/tests/chromaDB/test_hybrid_search_rag_integration.py -v")
    
    asyncio.run(run_tests())