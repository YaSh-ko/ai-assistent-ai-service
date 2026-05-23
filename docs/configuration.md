# Конфигурация Python AI Service

## Обзор

Все настройки сервиса управляются через переменные окружения, которые загружаются из файла `.env`. Конфигурация разделена на логические секции для удобства управления.

## Структура конфигурации

Конфигурация определена в `app/core/config.py` с использованием Pydantic Settings.

## Переменные окружения

### Основные настройки приложения

```bash
# Название и версия
APP_NAME="Python AI Service"
APP_VERSION="0.1.0"

# Режим отладки
DEBUG=False

# Уровень логирования: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# Корневой путь API (для reverse proxy)
ROOT_PATH=/ai
```

### Настройки моделей

#### Текущая модель по умолчанию

```bash
# Модель для использования: gigachat, gigachat_pro, gigachat_max, vllm
CURRENT_MODEL=gigachat_pro
```

#### GigaChat конфигурация

```bash
# Аутентификация (используйте ЛИБО credentials ЛИБО client_id/secret)
# Рекомендуется: client_id + client_secret
GIGACHAT_CLIENT_ID=your-client-id
GIGACHAT_CLIENT_SECRET=your-client-secret

# Альтернатива (не рекомендуется):
# GIGACHAT_CREDENTIALS=base64-encoded-credentials

# Scope для API
GIGACHAT_SCOPE=GIGACHAT_API_PERS

# Параметры для GigaChat Base
GIGACHAT_TEMPERATURE=0.3
GIGACHAT_MAX_TOKENS=1000

# Параметры для GigaChat Pro
GIGACHAT_PRO_TEMPERATURE=0.7
GIGACHAT_PRO_MAX_TOKENS=1500

# Параметры для GigaChat Max
GIGACHAT_MAX_TEMPERATURE=0.5
GIGACHAT_MAX_MAX_TOKENS=2000
```

**Описание параметров**:
- `GIGACHAT_CLIENT_ID` — ID клиента для OAuth
- `GIGACHAT_CLIENT_SECRET` — секрет клиента для OAuth
- `GIGACHAT_SCOPE` — область доступа API
- `TEMPERATURE` — креативность ответов (0.0-1.0)
  - 0.0-0.3: детерминированные ответы
  - 0.4-0.7: сбалансированные ответы
  - 0.8-1.0: креативные ответы
- `MAX_TOKENS` — максимальная длина ответа

#### vLLM конфигурация

```bash
# URL vLLM сервера
VLLM_API_URL=http://localhost:8000/v1

# Название модели
VLLM_MODEL_NAME=local-model

# API ключ (если требуется)
VLLM_API_KEY=

# Параметры генерации
VLLM_TEMPERATURE=0.7
VLLM_MAX_TOKENS=2000
VLLM_TOP_P=0.9

# Таймауты и повторы
VLLM_TIMEOUT=60
VLLM_RETRY_ATTEMPTS=3
```

**Описание параметров**:
- `VLLM_API_URL` — адрес vLLM сервера (OpenAI-совместимый API)
- `VLLM_MODEL_NAME` — имя загруженной модели
- `TOP_P` — nucleus sampling (0.0-1.0)
- `TIMEOUT` — таймаут запроса в секундах
- `RETRY_ATTEMPTS` — количество попыток при ошибке

### Настройки Reasoning

```bash
# Движок рассуждения по умолчанию: cot, reflection
DEFAULT_REASONING_ENGINE=cot

# Chain-of-Thought конфигурация
COT_MAX_REASONING_DEPTH=4
COT_MAX_CLARIFYING_QUESTIONS=5
COT_ENABLE_VERIFICATION=True
COT_NEO4J_MAX_DEPTH=3
COT_TIMEOUT_PER_STEP=30

# Reflection/Critic Loops конфигурация
REFLECTION_MAX_ITERATIONS=3
REFLECTION_QUALITY_THRESHOLD=0.8
REFLECTION_CRITIQUE_TEMP=0.3
REFLECTION_REFINEMENT_TEMP=0.7
```

**Описание параметров**:

**CoT (Chain-of-Thought)**:
- `MAX_REASONING_DEPTH` — максимальная глубина рассуждения
- `MAX_CLARIFYING_QUESTIONS` — макс. уточняющих вопросов
- `ENABLE_VERIFICATION` — включить шаг верификации
- `NEO4J_MAX_DEPTH` — глубина поиска в графе
- `TIMEOUT_PER_STEP` — таймаут на шаг (секунды)

**Reflection**:
- `MAX_ITERATIONS` — максимум итераций улучшения
- `QUALITY_THRESHOLD` — порог качества (0.0-1.0)
- `CRITIQUE_TEMP` — температура для критики
- `REFINEMENT_TEMP` — температура для улучшения

### Настройки баз данных

#### PostgreSQL

```bash
# Параметры подключения
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password
POSTGRES_DB=your-database

# Или connection string
DATABASE_URL=postgresql://user:password@host:port/database
```

**Описание параметров**:
- `POSTGRES_HOST` — хост PostgreSQL
- `POSTGRES_PORT` — порт (обычно 5432)
- `POSTGRES_USER` — имя пользователя
- `POSTGRES_PASSWORD` — пароль
- `POSTGRES_DB` — имя базы данных
- `DATABASE_URL` — полная строка подключения (альтернатива)

#### Neo4j

```bash
# Параметры подключения
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password

# Настройки памяти
NEO4J_PAGECACHE_SIZE=512M
NEO4J_HEAP_INITIAL=512M
NEO4J_HEAP_MAX=1G
```

**Описание параметров**:
- `NEO4J_URI` — URI подключения (bolt://, bolt+s://, neo4j://)
- `NEO4J_USERNAME` — имя пользователя
- `NEO4J_PASSWORD` — пароль
- `PAGECACHE_SIZE` — размер page cache
- `HEAP_INITIAL/MAX` — размер heap памяти JVM

#### Redis

```bash
# URL подключения
REDIS_URL=redis://localhost:6379/0
```

**Описание параметров**:
- `REDIS_URL` — полный URL подключения к Redis

### Настройки векторных баз данных

#### Выбор векторной БД

```bash
# Тип векторной БД: chroma, milvus
VECTOR_STORE_TYPE=chroma
```

#### ChromaDB

```bash
# Серверный режим
CHROMA_SERVER_HOST=localhost
CHROMA_SERVER_PORT=8001
CHROMA_SERVER_SSL=False

# Локальный режим
CHROMA_DB_PATH=./chroma_db

# Коллекция
CHROMA_COLLECTION_NAME=chat_history

# Метрика расстояния: cosine, l2, ip
CHROMA_DISTANCE_FUNCTION=cosine
```

**Описание параметров**:
- `CHROMA_SERVER_HOST` — хост ChromaDB сервера
- `CHROMA_SERVER_PORT` — порт сервера
- `CHROMA_SERVER_SSL` — использовать SSL
- `CHROMA_DB_PATH` — путь для локального хранения
- `DISTANCE_FUNCTION` — функция расстояния

#### Milvus

```bash
# Параметры подключения
MILVUS_HOST=localhost
MILVUS_PORT=19530

# Аутентификация (опционально)
MILVUS_USER=
MILVUS_PASSWORD=

# Коллекция
MILVUS_COLLECTION=chat_history
```

**Описание параметров**:
- `MILVUS_HOST` — хост Milvus сервера
- `MILVUS_PORT` — порт (обычно 19530)
- `MILVUS_USER` — имя пользователя (если требуется)
- `MILVUS_PASSWORD` — пароль (если требуется)
- `MILVUS_COLLECTION` — имя коллекции

### Настройки эмбеддингов

```bash
# Модель эмбеддингов
EMBEDDING_MODEL=EmbeddingsGigaR

# Размерность векторов
EMBEDDING_DIMENSION=1024
```

**Описание параметров**:
- `EMBEDDING_MODEL` — модель для генерации эмбеддингов
- `EMBEDDING_DIMENSION` — размерность векторов (должна соответствовать модели)

### Настройки поиска

#### Chunking (разбиение текста)

```bash
# Размер чанка
CHUNK_SIZE=500

# Перекрытие между чанками
CHUNK_OVERLAP=50

# Тип splitter: recursive, character, token
TEXT_SPLITTER_TYPE=recursive
```

**Описание параметров**:
- `CHUNK_SIZE` — размер фрагмента текста (символы)
- `CHUNK_OVERLAP` — перекрытие между фрагментами
- `TEXT_SPLITTER_TYPE` — алгоритм разбиения

#### Retrieval (извлечение)

```bash
# Количество результатов
TOP_K_RESULTS=5

# Порог схожести (0.0-1.0)
SIMILARITY_THRESHOLD=0.7

# Метрика расстояния: cosine, l2, ip
DISTANCE_METRIC=cosine
```

**Описание параметров**:
- `TOP_K_RESULTS` — количество возвращаемых документов
- `SIMILARITY_THRESHOLD` — минимальная схожесть для включения
- `DISTANCE_METRIC` — метрика для векторного поиска

#### Гибридный поиск

```bash
# Веса для гибридного поиска (должны в сумме давать 1.0)
HYBRID_BM25_WEIGHT=0.5
HYBRID_VECTOR_WEIGHT=0.5

# Параметры BM25
BM25_K1=1.5
BM25_B=0.75
```

**Описание параметров**:
- `HYBRID_BM25_WEIGHT` — вес BM25 поиска (0.0-1.0)
- `HYBRID_VECTOR_WEIGHT` — вес векторного поиска (0.0-1.0)
- `BM25_K1` — параметр насыщения термов
- `BM25_B` — параметр нормализации длины документа

### Настройки сессий

```bash
# Время жизни сессии (секунды)
SESSION_TIMEOUT=3600

# Максимальная длина контекста
MAX_CONTEXT_LENGTH=10

# Провайдер кэша: redis, memory
CACHE_PROVIDER=redis
```

**Описание параметров**:
- `SESSION_TIMEOUT` — TTL сессии в секундах
- `MAX_CONTEXT_LENGTH` — макс. сообщений в контексте
- `CACHE_PROVIDER` — где хранить кэш сессий

### Настройки LangSmith (мониторинг)

```bash
# Включить трейсинг
LANGSMITH_TRACING=true

# Endpoint
LANGSMITH_ENDPOINT=https://api.smith.langchain.com

# API ключ
LANGSMITH_API_KEY=your-api-key

# Название проекта
LANGSMITH_PROJECT=your-project
```

**Описание параметров**:
- `LANGSMITH_TRACING` — включить/выключить трейсинг
- `LANGSMITH_ENDPOINT` — URL LangSmith API
- `LANGSMITH_API_KEY` — ключ доступа
- `LANGSMITH_PROJECT` — имя проекта для группировки

## Примеры конфигураций

### Development (разработка)

```bash
# Основное
DEBUG=True
LOG_LEVEL=DEBUG

# Модель
CURRENT_MODEL=gigachat

# БД (локальные)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
NEO4J_URI=bolt://localhost:7687
VECTOR_STORE_TYPE=chroma
CHROMA_SERVER_HOST=localhost
CHROMA_SERVER_PORT=8001

# Reasoning
DEFAULT_REASONING_ENGINE=cot
```

### Staging (тестирование)

```bash
# Основное
DEBUG=False
LOG_LEVEL=INFO

# Модель
CURRENT_MODEL=gigachat_pro

# БД (тестовые серверы)
POSTGRES_HOST=staging-db.example.com
NEO4J_URI=bolt+s://staging-neo4j.example.com:7687
VECTOR_STORE_TYPE=milvus
MILVUS_HOST=staging-milvus.example.com

# Reasoning
DEFAULT_REASONING_ENGINE=reflection
```

### Production (продакшн)

```bash
# Основное
DEBUG=False
LOG_LEVEL=WARNING

# Модель
CURRENT_MODEL=gigachat_max

# БД (продакшн серверы)
DATABASE_URL=postgresql://user:pass@prod-db.example.com:5432/prod_db
NEO4J_URI=bolt+s://prod-neo4j.example.com:7687
VECTOR_STORE_TYPE=milvus
MILVUS_HOST=prod-milvus.example.com
MILVUS_PORT=19530

# Кэширование
REDIS_URL=redis://prod-redis.example.com:6379/0

# Reasoning
DEFAULT_REASONING_ENGINE=cot
COT_TIMEOUT_PER_STEP=60

# Мониторинг
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=prod-ai-service
```

## Валидация конфигурации

### Автоматическая валидация

Pydantic автоматически валидирует:
- Типы данных
- Обязательные поля
- Диапазоны значений
- Форматы строк

### Кастомная валидация

В `app/core/config.py` есть валидаторы:

```python
@model_validator(mode='after')
def validate_weights(self) -> 'Settings':
    """Проверка что веса в сумме дают 1.0"""
    bm25_w = self.SEARCH_CONFIG.get("bm25_weight", 0.5)
    vector_w = self.SEARCH_CONFIG.get("vector_weight", 0.5)
    if abs(bm25_w + vector_w - 1.0) > 1e-6:
        raise ValueError("Веса должны в сумме давать 1.0")
    return self
```

## Переопределение конфигурации

### Через переменные окружения

```bash
# Переопределить одну переменную
CURRENT_MODEL=gigachat_max python3 -m uvicorn app.main:app

# Переопределить несколько
DEBUG=True LOG_LEVEL=DEBUG python3 -m uvicorn app.main:app
```

### Через .env файлы

```bash
# Использовать другой .env файл
cp .env.production .env
python3 -m uvicorn app.main:app
```

### Через Docker

```yaml
# docker-compose.yml
services:
  api:
    environment:
      - CURRENT_MODEL=gigachat_pro
      - DEBUG=False
      - DATABASE_URL=postgresql://...
```

## Безопасность конфигурации

### Секреты

**НЕ коммитьте в Git**:
- `.env` файл
- Пароли
- API ключи
- Токены

**Используйте**:
- `.env.example` с примерами (без реальных значений)
- Secrets management (Vault, AWS Secrets Manager)
- Environment variables в CI/CD

### Права доступа

```bash
# Ограничить доступ к .env
chmod 600 .env

# Владелец: только чтение/запись
# Группа: нет доступа
# Остальные: нет доступа
```

## Проверка конфигурации

### Скрипт проверки

```bash
# Проверить текущую конфигурацию
python3 scripts/check_config.py
```

### Вывод конфигурации

```python
from app.core.config import settings

# Вывести все настройки (без секретов)
print(settings.dict(exclude={'GIGACHAT_CLIENT_SECRET', 'POSTGRES_PASSWORD'}))
```

## Troubleshooting

### Проблема: Конфигурация не загружается

**Решение**:
1. Проверьте путь к `.env` файлу
2. Убедитесь что файл в кодировке UTF-8
3. Проверьте синтаксис (нет пробелов вокруг `=`)

### Проблема: Неверные значения

**Решение**:
1. Проверьте типы данных
2. Убедитесь что числа не в кавычках (кроме строк)
3. Проверьте булевы значения: `True`/`False` (с заглавной)

### Проблема: Секреты не работают

**Решение**:
1. Проверьте что нет пробелов в начале/конце
2. Убедитесь что используете правильный формат
3. Для GigaChat: используйте CLIENT_ID/SECRET, не CREDENTIALS

## Ссылки

- [Architecture](./architecture.md)
- [Troubleshooting](./TROUBLESHOOTING.md)
- [Module Replacement](./modules/)
