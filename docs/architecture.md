# Архитектура Python AI Service

## Обзор

Python AI Service — это модульный AI-сервис для работы с большими языковыми моделями (LLM), векторными базами данных и графовыми хранилищами. Сервис построен на принципах чистой архитектуры с четким разделением слоев и использованием интерфейсов для обеспечения гибкости и тестируемости.

## Архитектурная диаграмма

```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                     │
│  /api/v1/chat, /api/v1/assistants, /api/v1/threads         │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────┐
│                    Service Layer                             │
│  • ReasoningService  • SessionManager  • ChatService        │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────┐
│                    Chain Layer                               │
│  • RAGChain (Retrieval-Augmented Generation)                │
│  • CAGChain (Context-Augmented Generation)                  │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────┐
│                  Factory Layer                               │
│  • ModelFactory  • ReasoningFactory  • DatabaseFactory      │
│  • SearchFactory                                            │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────┐
│                  Provider Layer                              │
│  • Model Providers (GigaChat, vLLM)                         │
│  • Reasoning Providers (CoT, Reflection)                    │
│  • Database Providers (PostgreSQL, Neo4j, Chroma, Milvus)  │
│  • Search Providers (Vector, BM25, Hybrid)                  │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────┐
│              Data Access Layer (DAL)                         │
│  • Repositories (Session, Entry, Embedding, Graph)          │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────┐
│                External Services                             │
│  • PostgreSQL  • Neo4j  • ChromaDB/Milvus  • Redis         │
│  • GigaChat API  • vLLM Server                              │
└─────────────────────────────────────────────────────────────┘
```

## Основные компоненты

### 1. API Layer (Слой API)

**Расположение**: `app/api/`

**Назначение**: Обработка HTTP-запросов, валидация входных данных, маршрутизация.

**Ключевые файлы**:
- `app/api/routes.py` — основные маршруты
- `app/api/chat.py` — эндпоинты чата
- `app/api/assistants.py` — управление ассистентами
- `app/api/threads.py` — управление потоками диалогов
- `app/api/deps.py` — зависимости FastAPI

**Технологии**: FastAPI, Pydantic

### 2. Service Layer (Слой сервисов)

**Расположение**: `app/services/`, `app/chat/`

**Назначение**: Бизнес-логика, оркестрация компонентов.

**Ключевые компоненты**:

#### ReasoningService
- Выбор и управление движками рассуждения
- Выполнение процесса reasoning
- Сохранение истории рассуждений

#### SessionManager
- Управление сессиями чата
- Сохранение истории сообщений
- Кэширование сессий

#### ChatService
- Обработка сообщений чата
- Интеграция с RAG/CAG chains
- Стриминг ответов

### 3. Chain Layer (Слой цепочек)

**Расположение**: `app/chains/`

**Назначение**: Реализация паттернов обработки запросов.

**Компоненты**:

#### RAGChain (Retrieval-Augmented Generation)
```python
Запрос → Поиск контекста → Генерация ответа
         (Vector/BM25)      (LLM + Context)
```

**Функции**:
- Поиск релевантных документов
- Формирование контекста
- Генерация ответа с учетом контекста

#### CAGChain (Context-Augmented Generation)
```python
Запрос → Анализ графа → Генерация ответа
         (Neo4j)         (LLM + Graph Context)
```

**Функции**:
- Извлечение связей из графа знаний
- Обогащение контекста графовыми данными
- Генерация ответа с учетом связей

### 4. Factory Layer (Слой фабрик)

**Расположение**: `app/factory/`

**Назначение**: Создание и управление экземплярами компонентов.

**Фабрики**:

#### ModelFactory
- Создание провайдеров моделей
- Singleton pattern для переиспользования
- Управление жизненным циклом

#### ReasoningFactory
- Создание движков рассуждения
- Конфигурация reasoning engines
- Кэширование экземпляров

#### DatabaseFactory
- Создание подключений к БД
- Управление пулами соединений
- Health checks

#### SearchFactory
- Создание поисковых провайдеров
- Конфигурация гибридного поиска
- Управление индексами

### 5. Provider Layer (Слой провайдеров)

**Расположение**: `app/providers/`

**Назначение**: Реализация интерфейсов для внешних сервисов.

#### Model Providers (`app/providers/models/`)

**Интерфейс**: `IModelProvider`

**Реализации**:
- `GigaChatProvider` — интеграция с GigaChat API
  - Поддержка версий: Base, Pro, Max
  - OAuth аутентификация
  - Стриминг ответов
  
- `VLLMProvider` — интеграция с vLLM сервером
  - Локальные модели
  - OpenAI-совместимый API
  - Высокая производительность

**Методы**:
```python
async def generate(prompt, **kwargs) -> ModelResponse
async def stream(prompt, **kwargs) -> AsyncGenerator[StreamChunk]
async def is_available() -> bool
```

#### Reasoning Providers (`app/providers/reasoning/`)

**Интерфейс**: `IReasoningEngine`

**Реализации**:
- `CoTProvider` — Chain-of-Thought рассуждение
  - 4 шага: Understand → Plan → Execute → Verify
  - Структурированный процесс
  
- `ReflectionProvider` — Reflection/Critic Loops
  - Итеративное улучшение ответа
  - Самокритика и рефлексия
  - Оценка качества

**Методы**:
```python
async def reason(query, context, **kwargs) -> ReasoningResult
def get_reasoning_steps() -> List[ReasoningStep]
def get_metadata() -> Dict[str, Any]
```

#### Database Providers (`app/providers/databases/`)

**Реляционные БД**:
- `PostgresProvider` — PostgreSQL
  - Asyncpg для асинхронных операций
  - Пулы соединений
  - Транзакции

**Графовые БД**:
- `Neo4jProvider` — Neo4j
  - Cypher запросы
  - Управление графом знаний
  - Поиск связей

**Векторные БД**:
- `ChromaProvider` — ChromaDB
  - Встраиваемая/серверная
  - Простая настройка
  
- `MilvusProvider` — Milvus
  - Высокая производительность
  - Масштабируемость
  - Продакшн-ready

#### Search Providers (`app/providers/search/`)

**Интерфейс**: `ISearchProvider`

**Реализации**:
- `VectorSearchProvider` — векторный поиск
- `BM25SearchProvider` — полнотекстовый поиск
- `HybridSearchProvider` — гибридный поиск
- `GraphSearchProvider` — поиск по графу

### 6. Data Access Layer (Слой доступа к данным)

**Расположение**: `app/data_access/`

**Назначение**: Абстракция работы с хранилищами данных.

**Репозитории**:

#### PostgreSQL Repositories (`app/data_access/postgresql/`)
- `SessionRepository` — сессии пользователей
- `EntryRepository` — записи дневника
- `ChatSessionRepository` — сессии чата
- `ThreadRepository` — потоки диалогов

#### Neo4j Repositories (`app/data_access/neo4j/`)
- `GraphRepository` — работа с графом знаний
- Создание узлов и связей
- Поиск паттернов

#### Vector Repositories (`app/data_access/repositories/`)
- `EmbeddingRepository` — управление эмбеддингами
- Добавление документов
- Поиск похожих

### 7. Core Layer (Ядро)

**Расположение**: `app/core/`

**Компоненты**:

#### Configuration (`app/core/config.py`)
- Загрузка переменных окружения
- Валидация конфигурации
- Настройки по умолчанию

#### Interfaces (`app/interfaces/`)
- `IModelProvider` — интерфейс моделей
- `IReasoningEngine` — интерфейс reasoning
- `IVectorStore` — интерфейс векторных БД
- `IRelationalDatabase` — интерфейс реляционных БД
- `IGraphDatabase` — интерфейс графовых БД
- `ISearchProvider` — интерфейс поиска

#### Monitoring (`app/monitoring/`)
- `ModelMetrics` — метрики моделей
- `ReasoningMetrics` — метрики reasoning
- Логирование

## Потоки данных

### 1. Простой запрос к LLM

```
User Request
    ↓
API Layer (FastAPI)
    ↓
ChatService
    ↓
ModelFactory.get_model()
    ↓
GigaChatProvider.generate()
    ↓
GigaChat API
    ↓
Response → User
```

### 2. RAG запрос (с контекстом)

```
User Request
    ↓
API Layer
    ↓
ChatService
    ↓
RAGChain
    ├→ SearchFactory.create_search()
    │   ├→ VectorSearchProvider
    │   │   └→ ChromaDB/Milvus
    │   └→ BM25SearchProvider
    │       └→ PostgreSQL
    ↓
Retrieved Context
    ↓
ModelFactory.get_model()
    ↓
GigaChatProvider.generate(prompt + context)
    ↓
Response → User
```

### 3. Reasoning запрос

```
User Request
    ↓
API Layer
    ↓
ReasoningService
    ↓
ReasoningFactory.get_reasoning_engine()
    ↓
CoTProvider / ReflectionProvider
    ├→ Step 1: Understand
    ├→ Step 2: Plan
    ├→ Step 3: Execute
    │   └→ ModelProvider.generate()
    └→ Step 4: Verify
    ↓
ReasoningResult
    ↓
Response → User
```

## Принципы архитектуры

### 1. Разделение ответственности (Separation of Concerns)
- Каждый слой имеет четкую ответственность
- Минимальная связанность между слоями
- Высокая когезия внутри слоев

### 2. Dependency Inversion (Инверсия зависимостей)
- Зависимость от абстракций (интерфейсов)
- Не зависимость от конкретных реализаций
- Легкая замена компонентов

### 3. Factory Pattern (Паттерн Фабрика)
- Централизованное создание объектов
- Управление жизненным циклом
- Singleton для переиспользования

### 4. Repository Pattern (Паттерн Репозиторий)
- Абстракция доступа к данным
- Независимость от конкретной БД
- Упрощение тестирования

### 5. Strategy Pattern (Паттерн Стратегия)
- Взаимозаменяемые алгоритмы
- Выбор стратегии в runtime
- Расширяемость

## Масштабируемость

### Горизонтальное масштабирование

**API Layer**:
- Stateless дизайн
- Балансировка нагрузки (nginx, HAProxy)
- Множество инстансов FastAPI

**Service Layer**:
- Асинхронная обработка
- Очереди задач (Celery, RQ)
- Кэширование (Redis)

**Database Layer**:
- Read replicas для PostgreSQL
- Sharding для Milvus
- Кластер Neo4j

### Вертикальное масштабирование

- Увеличение ресурсов серверов
- GPU для inference (vLLM)
- Больше памяти для кэшей

## Безопасность

### Аутентификация и авторизация
- API ключи
- OAuth 2.0 для GigaChat
- JWT токены для пользователей

### Защита данных
- Шифрование в transit (TLS/SSL)
- Шифрование в rest (PostgreSQL encryption)
- Маскирование PII в логах

### Rate Limiting
- Ограничение запросов к API
- Защита от DDoS
- Квоты на пользователя

## Мониторинг и наблюдаемость

### Метрики
- Latency моделей
- Throughput API
- Использование ресурсов
- Ошибки и их типы

### Логирование
- Структурированные логи (JSON)
- Уровни: DEBUG, INFO, WARNING, ERROR
- Централизованное хранение (ELK, Loki)

### Трейсинг
- Distributed tracing (Jaeger, Zipkin)
- Отслеживание запросов через систему
- Профилирование производительности

## Тестирование

### Уровни тестирования

**Unit Tests**:
- Тестирование отдельных функций
- Моки для зависимостей
- Быстрое выполнение

**Integration Tests**:
- Тестирование взаимодействия компонентов
- Реальные БД (test containers)
- Проверка интеграций

**E2E Tests**:
- Тестирование полных сценариев
- Через API endpoints
- Проверка бизнес-логики

**Property-Based Tests**:
- Тестирование свойств системы
- Генерация тестовых данных
- Поиск edge cases

### Покрытие
- Цель: 80%+ для критичного кода
- Обязательно для новых фич
- CI/CD проверки

## Развертывание

### Docker
```yaml
services:
  api:
    image: python-ai-service:latest
    ports: ["8000:8000"]
  
  postgres:
    image: postgres:15
  
  neo4j:
    image: neo4j:5
  
  milvus:
    image: milvusdb/milvus:latest
```

### Kubernetes
- Deployment для API
- StatefulSet для БД
- ConfigMap для конфигурации
- Secrets для credentials

### CI/CD
- GitHub Actions / GitLab CI
- Автоматические тесты
- Сборка Docker образов
- Деплой в staging/production

## Зависимости

### Основные библиотеки
- **FastAPI** — веб-фреймворк
- **asyncpg** — PostgreSQL драйвер
- **neo4j** — Neo4j драйвер
- **chromadb** / **pymilvus** — векторные БД
- **aiohttp** — HTTP клиент
- **pydantic** — валидация данных

### AI/ML библиотеки
- **langchain** — LLM фреймворк
- **gigachat** — GigaChat SDK
- **sentence-transformers** — эмбеддинги

## Дальнейшее развитие

### Планируемые улучшения
1. Добавление новых reasoning алгоритмов
2. Поддержка дополнительных LLM провайдеров
3. Улучшение гибридного поиска
4. Расширение графа знаний
5. Оптимизация производительности

### Рефакторинг
1. Миграция на Pydantic v2
2. Улучшение типизации
3. Оптимизация запросов к БД
4. Кэширование на разных уровнях

## Ссылки

- [Configuration Guide](./configuration.md)
- [Troubleshooting](./TROUBLESHOOTING.md)
- [Module Replacement Guides](./modules/)
- [Runbook](./runbook/)
