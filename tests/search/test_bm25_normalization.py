import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.providers.search.bm25_provider import BM25Provider
from app.providers.search.hybrid_search_provider import normalize_bm25_scores, normalize_vector_scores
from app.core.config import settings

@pytest.mark.asyncio
async def test_bm25_normalization_criteria():
    """
    Тест 12: Нормализация скоров
    - [x] Получить BM25 скоры для набора документов
    - [x] Получить векторные скоры для тех же документов
    - [x] Проверить, что BM25 скоры нормализованы к диапазону
    - [x] Проверить, что векторные скоры нормализованы к диапазону
    - [x] Финальный скор в диапазоне
    """
    print("\n" + "="*60)
    print("ТЕСТ: Нормализация скоров BM25 и векторов")
    print("="*60)

    # 1. Подготовка моков
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    
    # Мокаем статистику (N=100, avgdl=50)
    mock_pool.fetchrow = AsyncMock(return_value={'n': 100, 'avgdl': 50.0})
    
    # Мокаем термины запроса и документы
    mock_pool.fetch = AsyncMock(side_effect=[
        [{'lexeme': 'test'}, {'lexeme': 'query'}],  # query terms
        [  # documents
            {
                'id': 1, 'user_id': 'u1', 'doc_length': 40, 'vec': "'test':1",
                'title': 'Doc 1', 'description': 'Desc 1', 'event_date': None, 'created_at': None, 'updated_at': None
            },
            {
                'id': 2, 'user_id': 'u1', 'doc_length': 60, 'vec': "'test':1 'query':2",
                'title': 'Doc 2', 'description': 'Desc 2', 'event_date': None, 'created_at': None, 'updated_at': None
            },
            {
                'id': 3, 'user_id': 'u1', 'doc_length': 50, 'vec': "'query':1",
                'title': 'Doc 3', 'description': 'Desc 3', 'event_date': None, 'created_at': None, 'updated_at': None
            }
        ]
    ])
    # Мокаем IDF
    mock_pool.fetchval = AsyncMock(side_effect=[10, 5])  # df for 'test', 'query'

    # Wrap pool in a mock provider
    mock_provider = MagicMock()
    mock_provider._ensure_connection = AsyncMock()
    mock_provider.pool = mock_pool

    mock_lock = AsyncMock()
    mock_lock.__aenter__ = AsyncMock(return_value=None)
    mock_lock.__aexit__ = AsyncMock(return_value=None)

    from unittest.mock import patch
    with patch('app.providers.databases.postgres_provider.PostgresProvider._query_lock', mock_lock):
        provider = BM25Provider(mock_provider)

        # 2. Получить BM25 скоры
        print("\n1. Получение BM25 скоров...")
        bm25_results = await provider.search(query="test query", user_id="u1", k=3)
    
    print(f"   Найдено документов: {len(bm25_results)}")
    for doc in bm25_results:
        print(f"   Doc {doc['id']}: raw_score = {doc['bm25_score']:.4f}")
    
    assert len(bm25_results) == 3
    assert all('bm25_score' in doc for doc in bm25_results)

    # 3. Получить векторные скоры (симуляция)
    print("\n2. Получение векторных скоров (симуляция)...")
    vector_results = [
        {'id': 1, 'score': 0.85, 'metadata': {'entry_id': 1}},
        {'id': 2, 'score': 0.92, 'metadata': {'entry_id': 2}},
        {'id': 3, 'score': 0.75, 'metadata': {'entry_id': 3}}
    ]
    for doc in vector_results:
        print(f"   Doc {doc['id']}: raw_score = {doc['score']:.4f}")

    # 4. Проверить нормализацию BM25
    print("\n3. Проверка нормализации BM25...")
    normalized_bm25 = normalize_bm25_scores(bm25_results)
    
    bm25_scores = [doc['normalized_score'] for doc in normalized_bm25]
    print(f"   Нормализованные скоры BM25: {[f'{s:.4f}' for s in bm25_scores]}")
    
    assert min(bm25_scores) == 0.0, "Минимальный нормализованный скор должен быть 0.0"
    assert max(bm25_scores) == 1.0, "Максимальный нормализованный скор должен быть 1.0"
    assert all(0.0 <= s <= 1.0 for s in bm25_scores), "Все скоры должны быть в диапазоне [0, 1]"
    print("   ✓ BM25 скоры успешно нормализованы к диапазону [0, 1]")

    # 5. Проверить нормализацию векторов
    print("\n4. Проверка нормализации векторов...")
    normalized_vector = normalize_vector_scores(vector_results)
    
    vector_scores = [doc['normalized_score'] for doc in normalized_vector]
    print(f"   Нормализованные векторные скоры: {[f'{s:.4f}' for s in vector_scores]}")
    
    assert min(vector_scores) == 0.0
    assert max(vector_scores) == 1.0
    assert all(0.0 <= s <= 1.0 for s in vector_scores)
    print("   ✓ Векторные скоры успешно нормализованы к диапазону [0, 1]")

    # 6. Проверка финального скора
    print("\n5. Проверка финального скора...")
    
    # Объединяем результаты (упрощенно)
    final_results = []
    bm25_map = {doc['id']: doc['normalized_score'] for doc in normalized_bm25}
    vector_map = {doc['id']: doc['normalized_score'] for doc in normalized_vector}
    
    bm25_weight = 0.3
    vector_weight = 0.7
    
    print(f"   Веса: BM25={bm25_weight}, Vector={vector_weight}")
    
    for doc_id in [1, 2, 3]:
        b_score = bm25_map.get(doc_id, 0)
        v_score = vector_map.get(doc_id, 0)
        final_score = (b_score * bm25_weight) + (v_score * vector_weight)
        
        final_results.append({
            'id': doc_id,
            'final_score': final_score,
            'bm25_norm': b_score,
            'vector_norm': v_score
        })
        print(f"   Doc {doc_id}: final_score = {final_score:.4f} (B:{b_score:.2f} * {bm25_weight} + V:{v_score:.2f} * {vector_weight})")

    final_scores = [r['final_score'] for r in final_results]
    
    # Проверка диапазона финального скора
    # Теоретический максимум = 1.0 * weight + 1.0 * weight = sum(weights)
    # Если веса не суммируются в 1, то диапазон может быть другим.
    # В hybrid_search_provider веса берутся из конфига.
    # Здесь мы проверяем просто корректность вычисления и диапазон [0, sum(weights)]
    
    max_possible_score = bm25_weight + vector_weight
    assert all(0.0 <= s <= max_possible_score for s in final_scores)
    print(f"   ✓ Финальные скоры находятся в допустимом диапазоне [0, {max_possible_score}]")

    print("\n" + "="*60)
    print("✅ ТЕСТ ЗАВЕРШЕН УСПЕШНО")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_bm25_normalization_criteria())
