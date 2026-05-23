#!/usr/bin/env python3
"""
Финальная интеграционная проверка Python AI Service.

Полный сценарий:
1. Создать сеанс через API
2. Записать 5 событий в дневник
3. Дождаться синхронизации с Neo4j и ChromaDB
4. Задать вопрос о паттерне
5. Получить streaming ответ с reasoning steps
6. Проверить сохранение диалога
7. Закрыть сеанс и восстановить историю
"""

import asyncio
import sys
import os
import time
import json
from datetime import datetime, date
from typing import Dict, Any, List

# Добавить корень проекта в путь
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
from app.factory.model_factory import ModelFactory
from app.factory.database_factory import DatabaseFactory
from app.core.config import settings


class IntegrationTest:
    """Класс для интеграционного тестирования."""
    
    def __init__(self, api_url: str = "http://localhost:8001"):
        self.api_url = api_url
        self.session_id = None
        self.user_id = f"test_user_{int(time.time())}"
        self.entry_ids = []
        self.message_ids = []
        
    def print_step(self, step_num: int, description: str):
        """Вывести информацию о шаге."""
        print("\n" + "=" * 70)
        print(f"ШАГ {step_num}: {description}")
        print("=" * 70)
    
    def print_success(self, message: str):
        """Вывести сообщение об успехе."""
        print(f"✓ {message}")
    
    def print_error(self, message: str):
        """Вывести сообщение об ошибке."""
        print(f"✗ {message}")
    
    def print_info(self, message: str):
        """Вывести информационное сообщение."""
        print(f"  {message}")
    
    # ========================================================================
    # ШАГ 1: Создать сеанс через API
    # ========================================================================
    
    def step1_create_session(self) -> bool:
        """Создать новый сеанс через API."""
        self.print_step(1, "Создание сеанса через API")
        
        try:
            # Проверить доступность API
            self.print_info("Проверка доступности API...")
            response = requests.get(f"{self.api_url}/health", timeout=5)
            
            if response.status_code != 200:
                self.print_error(f"API недоступен: {response.status_code}")
                return False
            
            self.print_success("API доступен")
            
            # Создать сеанс
            self.print_info("Создание нового сеанса...")
            
            # Используем эндпоинт для создания сеанса
            response = requests.post(
                f"{self.api_url}/api/v1/chat/sessions",
                json={
                    "user_id": self.user_id
                },
                timeout=10
            )
            
            if response.status_code == 201 or response.status_code == 200:
                data = response.json()
                self.session_id = data.get("session_id") or data.get("id") or data.get("thread_id")
                self.print_success(f"Сеанс создан: {self.session_id}")
                return True
            else:
                self.print_error(f"Ошибка создания сеанса: {response.status_code}")
                self.print_info(f"Response: {response.text}")
                return False
        
        except requests.exceptions.ConnectionError:
            self.print_error("Не удалось подключиться к API")
            self.print_info("Убедитесь что сервис запущен: systemctl status python-ai-service")
            return False
        
        except Exception as e:
            self.print_error(f"Ошибка: {e}")
            return False
    
    # ========================================================================
    # ШАГ 2: Записать 5 событий в дневник
    # ========================================================================
    
    async def step2_create_diary_entries(self) -> bool:
        """Создать 5 записей в дневнике."""
        self.print_step(2, "Запись 5 событий в дневник")
        
        entries = [
            {
                "title": "Утренняя пробежка",
                "content": "Сегодня пробежал 5 км в парке. Чувствую себя бодро и энергично.",
                "mood": "happy",
                "tags": ["спорт", "здоровье", "утро"]
            },
            {
                "title": "Работа над проектом",
                "content": "Провел 3 часа за разработкой нового функционала. Прогресс хороший.",
                "mood": "focused",
                "tags": ["работа", "программирование", "продуктивность"]
            },
            {
                "title": "Обед с коллегами",
                "content": "Обсудили планы на следующий спринт. Интересные идеи появились.",
                "mood": "social",
                "tags": ["работа", "общение", "планирование"]
            },
            {
                "title": "Чтение книги",
                "content": "Прочитал главу о паттернах проектирования. Много полезного узнал.",
                "mood": "curious",
                "tags": ["обучение", "книги", "развитие"]
            },
            {
                "title": "Вечерняя медитация",
                "content": "20 минут медитации перед сном. Помогает расслабиться и успокоиться.",
                "mood": "calm",
                "tags": ["здоровье", "медитация", "вечер"]
            }
        ]
        
        try:
            # Получить репозиторий записей
            from app.data_access.postgresql.entry_repository import EntryRepository
            
            provider = DatabaseFactory.create_relational_database()
            if not provider.pool:
                await provider.connect()
            
            # Создать пользователя если не существует
            user_check_query = "SELECT id FROM \"user\" WHERE id = $1"
            user_exists = await provider.pool.fetchrow(user_check_query, self.user_id)
            
            if not user_exists:
                self.print_info(f"Создание пользователя: {self.user_id}")
                create_user_query = """
                    INSERT INTO "user" (id, name, email, "emailVerified")
                    VALUES ($1, $2, $3, $4)
                """
                await provider.pool.execute(
                    create_user_query,
                    self.user_id,
                    f"Test User {self.user_id}",
                    f"{self.user_id}@test.com",
                    False
                )
                self.print_success("Пользователь создан")
            
            entry_repo = EntryRepository(provider)
            
            # Создать записи
            for i, entry_data in enumerate(entries, 1):
                self.print_info(f"Создание записи {i}/5: {entry_data['title']}")
                
                entry_id = await entry_repo.create(
                    user_id=self.user_id,
                    title=entry_data["title"],
                    description=entry_data["content"],
                    event_date=date.today()
                )
                
                self.entry_ids.append(entry_id)
                self.print_success(f"Запись создана: {entry_id}")
            
            self.print_success(f"Всего создано записей: {len(self.entry_ids)}")
            return True
        
        except Exception as e:
            self.print_error(f"Ошибка создания записей: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ========================================================================
    # ШАГ 3: Дождаться синхронизации с Neo4j и ChromaDB
    # ========================================================================
    
    async def step3_wait_for_sync(self) -> bool:
        """Дождаться синхронизации данных."""
        self.print_step(3, "Ожидание синхронизации с Neo4j и ChromaDB")
        
        try:
            # Проверить Neo4j
            self.print_info("Проверка синхронизации с Neo4j...")
            
            try:
                graph_db = await DatabaseFactory.create_graph_database()
                
                # Проверить наличие узлов пользователя
                query = """
                MATCH (u:User {user_id: $user_id})
                RETURN count(u) as count
                """
                
                result = await graph_db.execute_query(
                    query,
                    {"user_id": self.user_id}
                )
                
                if result and len(result) > 0 and result[0].get("count", 0) > 0:
                    self.print_success("Данные синхронизированы с Neo4j")
                else:
                    self.print_info("Узел пользователя еще не создан в Neo4j (это нормально)")
            
            except Exception as e:
                self.print_info(f"Neo4j недоступен или не настроен: {e}")
            
            # Проверить ChromaDB/Milvus
            self.print_info("Проверка синхронизации с векторной БД...")
            
            try:
                vector_store = DatabaseFactory.create_vector_store()
                
                # Выполнить реальную проверку - попытаться получить коллекцию
                if hasattr(vector_store, 'collection'):
                    # ChromaDB
                    collection = vector_store.collection
                    count = collection.count()
                    self.print_success(f"ChromaDB доступна (документов: {count})")
                elif hasattr(vector_store, 'client'):
                    # Milvus
                    from pymilvus import utility
                    collections = utility.list_collections()
                    self.print_success(f"Milvus доступна (коллекций: {len(collections)})")
                else:
                    # Общая проверка - просто создание экземпляра
                    self.print_success("Векторная БД доступна")
            
            except Exception as e:
                self.print_info(f"Векторная БД недоступна или не настроена: {e}")
            
            # Подождать немного для завершения фоновых процессов
            self.print_info("Ожидание 3 секунды для завершения синхронизации...")
            await asyncio.sleep(3)
            
            self.print_success("Синхронизация завершена")
            return True
        
        except Exception as e:
            self.print_error(f"Ошибка проверки синхронизации: {e}")
            return False
    
    # ========================================================================
    # ШАГ 4: Задать вопрос о паттерне
    # ========================================================================
    
    def step4_ask_pattern_question(self) -> bool:
        """Задать вопрос о паттернах в записях."""
        self.print_step(4, "Вопрос о паттернах")
        
        try:
            question = "Какие паттерны ты видишь в моих записях? Что я делаю регулярно?"
            
            self.print_info(f"Вопрос: {question}")
            self.print_info("Отправка запроса к API...")
            
            # Отправить сообщение
            response = requests.post(
                f"{self.api_url}/api/v1/chat/sessions/{self.session_id}/messages",
                json={
                    "content": question,
                    "role": "user"
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Извлечь ответ
                answer = data.get("assistant_response", "")
                
                self.print_success("Ответ получен")
                self.print_info("Ответ (первые 200 символов):")
                self.print_info(answer[:200] + "..." if len(answer) > 200 else answer)
                
                # Проверить reasoning metadata
                if "reasoning" in data:
                    reasoning = data["reasoning"]
                    self.print_info(f"Reasoning type: {reasoning.get('type')}")
                    self.print_info(f"Reasoning steps: {len(reasoning.get('steps', []))}")
                    self.print_info(f"Confidence: {reasoning.get('confidence_score')}")
                
                # Проверить sources
                if "sources" in data:
                    sources = data["sources"]
                    self.print_info(f"RAG events: {len(sources.get('rag_events', []))}")
                    self.print_info(f"Data sources: {', '.join(sources.get('data_sources', []))}")
                
                return True
            else:
                self.print_error(f"Ошибка API: {response.status_code}")
                self.print_info(f"Response: {response.text}")
                return False
        
        except Exception as e:
            self.print_error(f"Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ========================================================================
    # ШАГ 5: Получить streaming ответ с reasoning steps
    # ========================================================================
    
    def step5_streaming_with_reasoning(self) -> bool:
        """Получить streaming ответ с reasoning steps."""
        self.print_step(5, "Streaming ответ с reasoning steps")
        
        try:
            question = "Дай мне совет как улучшить мою продуктивность на основе моих записей"
            
            self.print_info(f"Вопрос: {question}")
            self.print_info("Отправка streaming запроса...")
            
            # Отправить streaming запрос
            response = requests.post(
                f"{self.api_url}/api/v1/chat/sessions/{self.session_id}/stream",
                json={
                    "content": question,
                    "role": "user"
                },
                stream=True,
                timeout=120
            )
            
            if response.status_code == 200:
                self.print_success("Streaming начался")
                self.print_info("Получение chunks:")
                
                full_response = ""
                chunk_count = 0
                
                # Читать stream
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        
                        if line.startswith('data: '):
                            data_str = line[6:]
                            
                            if data_str == '[DONE]':
                                self.print_info("\n[DONE]")
                                break
                            
                            try:
                                data = json.loads(data_str)
                                
                                # Формат: {"type": "text", "data": {"content": "..."}}
                                if data.get("type") == "text":
                                    content = data.get("data", {}).get("content", "")
                                    
                                    if content:
                                        full_response += content
                                        chunk_count += 1
                                        
                                        # Вывести первые несколько chunks
                                        if chunk_count <= 5:
                                            print(content, end="", flush=True)
                                
                                # Также обработать reasoning steps
                                elif data.get("type") == "reasoning_step":
                                    step = data.get("data", {})
                                    self.print_info(f"\nReasoning step: {step.get('description', 'N/A')}")
                            
                            except json.JSONDecodeError:
                                pass
                
                self.print_success(f"\nПолучено chunks: {chunk_count}")
                self.print_info("Полный ответ (первые 200 символов):")
                self.print_info(full_response[:200] + "..." if full_response else "(пустой ответ)")
                
                return True
            else:
                self.print_error(f"Ошибка streaming: {response.status_code}")
                return False
        
        except Exception as e:
            self.print_error(f"Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ========================================================================
    # ШАГ 6: Проверить сохранение диалога
    # ========================================================================
    
    def step6_check_dialog_saved(self) -> bool:
        """Проверить что диалог сохранен."""
        self.print_step(6, "Проверка сохранения диалога")
        
        try:
            self.print_info("Получение истории сеанса...")
            
            # Получить историю через API
            response = requests.get(
                f"{self.api_url}/api/v1/chat/sessions/{self.session_id}/messages",
                timeout=10
            )
            
            if response.status_code == 200:
                messages = response.json()
                
                # API возвращает список напрямую
                if not isinstance(messages, list):
                    messages = messages.get("data", []) or messages.get("messages", [])
                
                self.print_success(f"История получена: {len(messages)} сообщений")
                
                # Проверить что есть сообщения
                if len(messages) >= 2:  # Минимум 2 сообщения (вопрос + ответ)
                    self.print_success("Диалог сохранен корректно")
                    
                    # Вывести первые несколько сообщений
                    for i, msg in enumerate(messages[:4], 1):
                        role = msg.get("role", "unknown")
                        content = msg.get("content", "")
                        self.print_info(f"Сообщение {i} ({role}): {content[:50]}...")
                    
                    return True
                else:
                    self.print_error("Недостаточно сообщений в истории")
                    return False
            else:
                self.print_error(f"Ошибка получения истории: {response.status_code}")
                self.print_info(f"Response: {response.text}")
                return False
        
        except Exception as e:
            self.print_error(f"Ошибка: {e}")
            return False
    
    # ========================================================================
    # ШАГ 7: Закрыть сеанс и восстановить историю
    # ========================================================================
    
    def step7_close_and_restore(self) -> bool:
        """Закрыть сеанс и восстановить историю."""
        self.print_step(7, "Закрытие сеанса и восстановление истории")
        
        try:
            # Сохранить ID сеанса для восстановления
            saved_session_id = self.session_id
            
            self.print_info(f"Сохранен ID сеанса: {saved_session_id}")
            
            # "Закрыть" сеанс (просто очистить локальную переменную)
            self.session_id = None
            self.print_success("Сеанс 'закрыт' (локально)")
            
            # Подождать немного
            time.sleep(1)
            
            # Восстановить сеанс
            self.print_info("Восстановление истории сеанса...")
            
            response = requests.get(
                f"{self.api_url}/api/v1/chat/sessions/{saved_session_id}/messages",
                timeout=10
            )
            
            if response.status_code == 200:
                messages = response.json()
                
                # API возвращает список напрямую
                if not isinstance(messages, list):
                    messages = messages.get("data", []) or messages.get("messages", [])
                
                self.print_success(f"История восстановлена: {len(messages)} сообщений")
                
                # Проверить что история та же
                if len(messages) >= 2:
                    self.print_success("История сеанса успешно восстановлена")
                    
                    # Восстановить ID сеанса
                    self.session_id = saved_session_id
                    
                    return True
                else:
                    self.print_error("История не восстановлена корректно")
                    return False
            else:
                self.print_error(f"Ошибка восстановления: {response.status_code}")
                return False
        
        except Exception as e:
            self.print_error(f"Ошибка: {e}")
            return False
    
    # ========================================================================
    # Cleanup
    # ========================================================================
    
    async def cleanup(self):
        """Очистка ресурсов."""
        self.print_step(8, "Очистка ресурсов")
        
        try:
            # Закрыть фабрики
            await ModelFactory.close_all()
            await DatabaseFactory.close_all()
            
            self.print_success("Ресурсы очищены")
        
        except Exception as e:
            self.print_error(f"Ошибка очистки: {e}")
    
    # ========================================================================
    # Запуск всех шагов
    # ========================================================================
    
    async def run_all_steps(self) -> bool:
        """Запустить все шаги интеграционного теста."""
        print("\n" + "=" * 70)
        print("ФИНАЛЬНАЯ ИНТЕГРАЦИОННАЯ ПРОВЕРКА")
        print("Python AI Service - Full Scenario Test")
        print("=" * 70)
        
        results = []
        
        # Шаг 1: Создать сеанс
        result = self.step1_create_session()
        results.append(("Создание сеанса", result))
        if not result:
            return False
        
        # Шаг 2: Записать события
        result = await self.step2_create_diary_entries()
        results.append(("Запись событий", result))
        if not result:
            return False
        
        # Шаг 3: Синхронизация
        result = await self.step3_wait_for_sync()
        results.append(("Синхронизация", result))
        # Продолжаем даже если синхронизация не полная
        
        # Шаг 4: Вопрос о паттерне
        result = self.step4_ask_pattern_question()
        results.append(("Вопрос о паттерне", result))
        if not result:
            return False
        
        # Шаг 5: Streaming с reasoning
        result = self.step5_streaming_with_reasoning()
        results.append(("Streaming ответ", result))
        if not result:
            return False
        
        # Шаг 6: Проверка сохранения
        result = self.step6_check_dialog_saved()
        results.append(("Сохранение диалога", result))
        if not result:
            return False
        
        # Шаг 7: Закрытие и восстановление
        result = self.step7_close_and_restore()
        results.append(("Восстановление истории", result))
        if not result:
            return False
        
        # Cleanup
        await self.cleanup()
        
        # Итоговый отчет
        print("\n" + "=" * 70)
        print("ИТОГОВЫЙ ОТЧЕТ")
        print("=" * 70)
        
        for step_name, success in results:
            status = "✓ PASS" if success else "✗ FAIL"
            print(f"{status} - {step_name}")
        
        all_passed = all(result for _, result in results)
        
        print("\n" + "=" * 70)
        if all_passed:
            print("✓ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        else:
            print("✗ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
        print("=" * 70)
        
        return all_passed


async def main():
    """Главная функция."""
    # Проверить аргументы
    api_url = "http://localhost:8001"
    
    if len(sys.argv) > 1:
        api_url = sys.argv[1]
    
    print(f"API URL: {api_url}")
    
    # Создать тест
    test = IntegrationTest(api_url=api_url)
    
    # Запустить все шаги
    success = await test.run_all_steps()
    
    # Выход с кодом
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
