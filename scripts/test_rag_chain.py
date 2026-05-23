"""
Скрипт для тестирования RAG Chain.
Запуск: python scripts/test_rag_chain.py
"""

import asyncio
import sys
sys.path.insert(0, '.')

from app.chains.rag_chain import RAGChain, RAGState
from app.core.complexity_classifier import get_complexity_classifier
from app.core.model_selector import ModelSelector
from app.factory.model_factory import ModelFactory


async def test_complexity_classification():
    """Тест классификации сложности запросов."""
    print("\n" + "="*60)
    print("ТЕСТ 1: Классификация сложности запросов")
    print("="*60)
    
    classifier = get_complexity_classifier()
    
    test_queries = [
        ("Привет!", "SIMPLE → vLLM"),
        ("Запиши, что сегодня я чувствую себя хорошо", "MEDIUM → GigaChat Pro"),
        ("Проанализируй мои записи за год и найди паттерны в настроении", "COMPLEX → GigaChat Max"),
    ]
    
    for query, expected in test_queries:
        result = classifier.classify(query)
        print(f"\n📝 Запрос: '{query}'")
        print(f"   Ожидание: {expected}")
        print(f"   Результат: {result.level.value.upper()} → {result.suggested_model}")
        print(f"   Уверенность: {result.confidence:.0%}")
        print(f"   Причина: {result.reasoning}")


async def test_model_selection():
    """Тест выбора модели."""
    print("\n" + "="*60)
    print("ТЕСТ 2: Выбор модели через ModelSelector")
    print("="*60)
    
    test_cases = [
        ("Как дела?", False, False),
        ("Запиши событие", False, False),
        ("Проанализируй паттерны", False, False),
        ("Секретный вопрос", True, False),  # prefer_privacy
    ]
    
    for query, privacy, speed in test_cases:
        result = ModelSelector.select_model_with_details(
            query=query,
            prefer_privacy=privacy,
            prefer_speed=speed
        )
        
        flags = []
        if privacy:
            flags.append("🔒 privacy")
        if speed:
            flags.append("⚡ speed")
        flags_str = f" [{', '.join(flags)}]" if flags else ""
        
        print(f"\n📝 Запрос: '{query}'{flags_str}")
        print(f"   Модель: {result.model_name}")
        print(f"   Сложность: {result.complexity.level.value}")
        print(f"   Причина: {result.reason}")


async def test_rag_state():
    """Тест структуры RAGState."""
    print("\n" + "="*60)
    print("ТЕСТ 3: Структура RAGState")
    print("="*60)
    
    initial_state: RAGState = {
        "question": "Какие паттерны в моём настроении?",
        "user_id": "test_user",
        "thread_id": "thread_123",
        "session_id": "session_456",
        "query_embedding": None,
        "search_results": [],
        "filtered_results": [],
        "context": "",
        "reasoning_steps": [],
        "graph_insights": [],
        "answer": "",
        "extracted_events": [],
        "complexity": "",
        "selected_model": "",
        "processing_time_ms": 0
    }
    
    print(f"✅ RAGState создан успешно")
    print(f"   Поля: {list(initial_state.keys())}")


async def test_rag_chain_initialization():
    """Тест инициализации RAGChain (без внешних зависимостей)."""
    print("\n" + "="*60)
    print("ТЕСТ 4: Инициализация RAGChain")
    print("="*60)
    
    # Минимальная инициализация с заглушками
    class MockDAL:
        pass
    
    class MockEmbeddingService:
        async def generate_embedding(self, text):
            return [0.0] * 1024
    
    try:
        chain = RAGChain(
            dal=MockDAL(),
            embedding_service=MockEmbeddingService()
        )
        
        print("✅ RAGChain инициализирован успешно")
        print(f"   search_top_k: {chain.search_top_k}")
        print(f"   rerank_top_k: {chain.rerank_top_k}")
        
        # Тест построения графа
        graph = chain.build_graph()
        print(f"✅ LangGraph граф построен")
        
    except Exception as e:
        print(f"❌ Ошибка инициализации: {e}")


async def test_classify_query_step():
    """Тест шага classify_query."""
    print("\n" + "="*60)
    print("ТЕСТ 5: Шаг classify_query()")
    print("="*60)
    
    class MockDAL:
        pass
    
    class MockEmbeddingService:
        pass
    
    chain = RAGChain(
        dal=MockDAL(),
        embedding_service=MockEmbeddingService()
    )
    
    state: RAGState = {
        "question": "Проанализируй мои записи и найди закономерности",
        "user_id": "test_user",
        "thread_id": "",
        "session_id": "",
        "query_embedding": None,
        "search_results": [],
        "filtered_results": [],
        "context": "",
        "reasoning_steps": [],
        "graph_insights": [],
        "answer": "",
        "extracted_events": [],
        "complexity": "",
        "selected_model": "",
        "processing_time_ms": 0
    }
    
    result_state = await chain.classify_query(state)
    
    print(f"📝 Запрос: '{state['question']}'")
    print(f"✅ Классификация: {result_state['complexity']}")
    print(f"✅ Выбранная модель: {result_state['selected_model']}")


async def main():
    """Запуск всех тестов."""
    print("\n" + "🚀 " + "="*56 + " 🚀")
    print("   ТЕСТИРОВАНИЕ RAG CHAIN")
    print("🚀 " + "="*56 + " 🚀")
    
    await test_complexity_classification()
    await test_model_selection()
    await test_rag_state()
    await test_rag_chain_initialization()
    await test_classify_query_step()
    
    print("\n" + "="*60)
    print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
