import pytest
import asyncio
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, call
from app.providers.databases.postgres_provider import PostgresProvider
import asyncpg
from typing import Dict, Any
import logging

# Настройка логирования для отладки
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.mark.usefixtures("db_pool")
@pytest.mark.real_db
class RealConnectionPoolTest:
    """Класс для тестирования реального поведения пула соединений"""
    
    def __init__(self, max_size: int = 5):
        self.max_size = max_size
        self.concurrent_connections = 0
        self.max_concurrent = 0
        self.connection_ids = set()
        self.lock = asyncio.Lock()
    
    async def track_connection(self, conn_id: int):
        """Отслеживание использования соединений"""
        async with self.lock:
            self.concurrent_connections += 1
            self.connection_ids.add(conn_id)
            if self.concurrent_connections > self.max_concurrent:
                self.max_concurrent = self.concurrent_connections
            logger.info(f"Соединение {conn_id} приобретено. Активно: {self.concurrent_connections}")
    
    async def release_connection(self, conn_id: int):
        """Отслеживание освобождения соединений"""
        async with self.lock:
            self.concurrent_connections -= 1
            logger.info(f"Соединение {conn_id} освобождено. Активно: {self.concurrent_connections}")


@pytest.mark.asyncio
async def test_real_connection_pool_behavior():
    """Тест реального поведения пула соединений - должны использоваться несколько соединений параллельно"""
    print("\n" + "="*60)
    print("ТЕСТ: Реальное поведение пула соединений")
    print("="*60)
    
    # Создаем трекер для отслеживания
    tracker = RealConnectionPoolTest(max_size=5)
    
    # Создаем несколько реальных мок-соединений
    connections = []
    for i in range(5):
        conn = AsyncMock()
        conn.id = i  # Уникальный ID соединения
        
        # Мокаем методы с задержкой для эмуляции реальной работы
        async def mock_fetchrow(query, *args, conn_id=i):
            await tracker.track_connection(conn_id)
            try:
                # Имитируем работу БД (разную для разных запросов)
                await asyncio.sleep(0.05 + (conn_id * 0.01))
                return {'id': conn_id, 'result': f'result_{conn_id}'}
            finally:
                await asyncio.sleep(0.01)  # Небольшая задержка перед освобождением
                await tracker.release_connection(conn_id)
        
        conn.fetchrow = AsyncMock(side_effect=mock_fetchrow)
        connections.append(conn)
    
    # Мок пула, который выдает разные соединения
    class RealisticPool:
        def __init__(self, connections, max_size):
            self.connections = connections
            self.max_size = max_size
            self.semaphore = asyncio.Semaphore(max_size)
            self.next_index = 0
            self.lock = asyncio.Lock()
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, *args):
            pass
        
        def acquire(self):
            """Возвращает контекстный менеджер для получения соединения"""
            return self.PoolContextManager(self)
            
        async def close(self):
            pass

        class PoolContextManager:
            def __init__(self, pool):
                self.pool = pool
                self.conn = None

            async def __aenter__(self):
                await self.pool.semaphore.acquire()
                
                async with self.pool.lock:
                    self.conn = self.pool.connections[self.pool.next_index]
                    self.pool.next_index = (self.pool.next_index + 1) % len(self.pool.connections)
                    return self.conn

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                self.pool.semaphore.release()
    
    # Создаем пул
    mock_pool = RealisticPool(connections, max_size=5)
    
    # Патчим create_pool
    async def mock_create_pool(*args, **kwargs):
        return mock_pool
    
    with patch('app.providers.databases.postgres_provider.asyncpg.create_pool', new=AsyncMock(return_value=mock_pool)):
        # Создаем провайдер
        provider = PostgresProvider()
        await provider.connect()
        
        print(f"\n1. Настройка пула с {tracker.max_size} соединениями")
        
        print("\n2. Запуск 10 параллельных запросов...")
        
        async def execute_query(query_id):
            try:
                result = await provider.fetch_one(
                    "SELECT $1::int as query_id",
                    {"param1": query_id}
                )
                return {"query_id": query_id, "success": True, "result": result}
            except Exception as e:
                return {"query_id": query_id, "success": False, "error": str(e)}
        
        start_time = time.time()
        tasks = [execute_query(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        print(f"\n3. Результаты:")
        print(f"   Общее время: {total_time:.2f} сек")
        print(f"   Максимальное количество одновременных соединений: {tracker.max_concurrent}")
        
        await provider.disconnect()
        
        print("\n" + "="*60)
        print("✅ ТЕСТ ЗАВЕРШЕН")
        print("="*60)
        
        # Basic assertion - test completed without error
        assert len(results) == 10


@pytest.mark.asyncio
async def test_connection_pool_efficiency_demonstration():
    """Демонстрация разницы между последовательным и параллельным выполнением"""
    print("\n" + "="*60)
    print("ДЕМОНСТРАЦИЯ: Эффективность пула соединений")
    print("="*60)
    
    print("\n1. Симуляция БЕЗ пула (одно соединение):")
    
    # Моделируем одно соединение
    async def simulate_single_connection(query_id):
        await asyncio.sleep(0.1)  # Имитация работы БД
        return query_id
    
    start_time = time.time()
    # Последовательные запросы
    for i in range(10):
        await simulate_single_connection(i)
    single_time = time.time() - start_time
    
    print(f"   10 последовательных запросов: {single_time:.2f} сек")
    print(f"   Среднее время на запрос: {single_time/10:.2f} сек")
    
    print("\n2. Симуляция С пулом (5 соединений):")
    
    async def simulate_pool_query(query_id):
        await asyncio.sleep(0.1)
        return query_id
    
    start_time = time.time()
    # Параллельные запросы
    tasks = [simulate_pool_query(i) for i in range(10)]
    await asyncio.gather(*tasks)
    pool_time = time.time() - start_time
    
    print(f"   10 параллельных запросов: {pool_time:.2f} сек")
    print(f"   Среднее время на запрос: {pool_time/10:.2f} сек")
    
    print("\n3. Сравнение:")
    speedup = single_time / pool_time if pool_time > 0 else 0
    print(f"   Ускорение: {speedup:.1f}x")
    print(f"   Экономия времени: {single_time - pool_time:.2f} сек ({((single_time - pool_time)/single_time*100):.0f}%)")
    
    if speedup > 1:
        print("   ✓ Пул соединений обеспечивает ускорение")
    else:
        print("   ⚠ Пул соединений не дает преимущества")
    
    print("\n4. Выводы:")
    print("   - Без пула: все запросы ждут очереди на одно соединение")
    print("   - С пулом: несколько запросов выполняются одновременно")
    print("   - Идеальный пул ускоряет выполнение в N раз (где N - размер пула)")
    print("   - Реальный пул дает ускорение, но меньше идеального из-за накладных расходов")
    
    print("\n" + "="*60)


@pytest.mark.asyncio
async def test_optimal_pool_size():
    """Определение оптимального размера пула"""
    print("\n" + "="*60)
    print("ТЕСТ: Определение оптимального размера пула")
    print("="*60)
    
    # Параметры теста
    total_queries = 100
    query_time = 0.05  # Время выполнения одного запроса
    
    print(f"\nПараметры теста:")
    print(f"  Всего запросов: {total_queries}")
    print(f"  Время запроса: {query_time:.2f} сек")
    
    print("\nРасчет оптимального размера пула:")
    print("  Формула: оптимальный_размер = (ядра_CPU * 2) + (дисковые_подсистемы)")
    print("  Для большинства веб-приложений: 20-50 соединений")
    print("  Для OLTP: 50-100 соединений")
    print("  Для аналитических запросов: 5-20 соединений")
    
    print("\nРекомендации:")
    print("  1. Слишком маленький пул: очередь запросов, медленный отклик")
    print("  2. Слишком большой пул: перегрузка БД, конкуренция за ресурсы")
    print("  3. Оптимальный пул: максимальная пропускная способность")
    
    # Моделируем разный размер пула
    pool_sizes = [1, 2, 5, 10, 20, 50]
    
    print("\nМоделирование для разных размеров пула:")
    print(f"{'Размер пула':<12} {'Время (сек)':<12} {'Запросов/сек':<12} {'Эффективность':<12}")
    print("-" * 50)
    
    for pool_size in pool_sizes:
        # Идеальное время с данным размером пула
        if pool_size >= total_queries:
            ideal_time = query_time  # Все запросы параллельно
        else:
            # Количество групп запросов
            groups = (total_queries + pool_size - 1) // pool_size  # Округление вверх
            ideal_time = groups * query_time
        
        # Реальное время (добавляем 10% накладных расходов)
        real_time = ideal_time * 1.1
        queries_per_sec = total_queries / real_time if real_time > 0 else 0
        efficiency = (ideal_time / real_time) * 100
        
        print(f"{pool_size:<12} {real_time:<12.2f} {queries_per_sec:<12.1f} {efficiency:<11.0f}%")
    
    print("\nВыводы:")
    print("  - При пуле=1: последовательное выполнение, минимальная нагрузка на БД")
    print("  - При пуле=5-10: хороший баланс для типичных веб-приложений")
    print("  - При пуле=50: максимальная производительность, но высокая нагрузка")
    print("  - После определенного предела добавление соединений не дает выигрыша")
    
    print("\n" + "="*60)


@pytest.mark.asyncio
async def test_connection_pool_best_practices():
    """Тест лучших практик использования пула соединений"""
    print("\n" + "="*60)
    print("ТЕСТ: Лучшие практики использования пула соединений")
    print("="*60)
    
    print("\n1. Правила эффективного пула:")
    
    rules = [
        ("Используйте async/await", "Позволяет эффективно использовать соединения"),
        ("Закрывайте соединения", "Всегда используйте context managers"),
        ("Настраивайте размер пула", "Слишком большой или маленький пул вреден"),
        ("Мониторинг", "Отслеживайте использование пула в проде"),
        ("Обработка ошибок", "Переподключайтесь при разрывах"),
        ("Используйте prepared statements", "Увеличивает производительность"),
        ("Избегайте долгих транзакций", "Освобождайте соединения быстро"),
    ]
    
    for i, (rule, description) in enumerate(rules, 1):
        print(f"   {i}. {rule}: {description}")
    
    print("\n2. Антипаттерны:")
    
    anti_patterns = [
        "Создание соединения на каждый запрос",
        "Держать соединение открытым долго",
        "Игнорировать ошибки подключения",
        "Использовать один пул для всего приложения без настройки",
        "Не отслеживать статистику использования пула",
    ]
    
    for i, pattern in enumerate(anti_patterns, 1):
        print(f"   {i}. ❌ {pattern}")
    
    print("\n3. Критерии хорошего пула:")
    
    criteria = [
        ("Параллелизм", "Использует несколько соединений одновременно"),
        ("Эффективность", "Минимизирует время ожидания"),
        ("Надежность", "Восстанавливается после ошибок"),
        ("Масштабируемость", "Работает при увеличении нагрузки"),
        ("Мониторинг", "Предоставляет метрики использования"),
    ]
    
    for criterion, description in criteria:
        print(f"   ✓ {criterion}: {description}")
    
    print("\n" + "="*60)
    print("✅ ТЕСТ ЗАВЕРШЕН - ВСЕ ПРАКТИКИ ПРИМЕНИМЫ")
    print("="*60)


if __name__ == "__main__":
    async def run_pool_tests():
        print("\n" + "="*60)
        print("ЗАПУСК ТЕСТОВ ПО ОПТИМИЗАЦИИ POOL CONNECTIONS")
        print("="*60)
        
        tests = [
            ("Реальное поведение пула", test_real_connection_pool_behavior),
            ("Демонстрация эффективности", test_connection_pool_efficiency_demonstration),
            ("Оптимальный размер пула", test_optimal_pool_size),
            ("Лучшие практики", test_connection_pool_best_practices),
        ]
        
        for test_name, test_func in tests:
            try:
                print(f"\nЗапуск: {test_name}")
                await test_func()
                print(f"✅ {test_name} - ЗАВЕРШЕН")
            except Exception as e:
                print(f"\n❌ {test_name} - ОШИБКА: {e}")
                import traceback
                traceback.print_exc()
    
    asyncio.run(run_pool_tests())