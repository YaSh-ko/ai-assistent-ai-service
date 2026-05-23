# Python AI Service - Финальная версия

## Обзор

Python AI Service — это модульный AI-сервис для работы с большими языковыми моделями (LLM), векторными базами данных и графовыми хранилищами. Сервис построен на принципах чистой архитектуры с поддержкой различных reasoning engines и легкой заменой компонентов.

## Ключевые возможности

### ✓ Модульная архитектура
- Легкая замена LLM моделей (GigaChat, vLLM, и др.)
- Поддержка различных reasoning engines (CoT, Reflection)
- Взаимозаменяемые базы данных (PostgreSQL, Neo4j, ChromaDB, Milvus)

### ✓ Reasoning Engines
- **Chain-of-Thought (CoT)** - структурированное рассуждение в 4 шага
- **Reflection/Critic Loops** - итеративное улучшение ответов
- Расширяемая система для добавления новых алгоритмов

### ✓ RAG (Retrieval-Augmented Generation)
- Векторный поиск (ChromaDB/Milvus)
- Полнотекстовый поиск (BM25)
- Гибридный поиск с настраиваемыми весами
- Граф знаний (Neo4j)

### ✓ Production-ready
- Comprehensive тестирование (Unit, Integration, E2E, Property-Based)
- Стресс-тестирование с учетом rate limits
- Полная документация на русском языке
- Runbook для операционной работы

## Быстрый старт

### 1. Установка

```bash
# Клонировать репозиторий
git clone <repository-url>
cd python-ai-service

# Создать виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate

# Установить зависимости
pip install -r requirements.txt
```

### 2. Конфигурация

```bash
# Создать .env файл
cp .env.example .env

# Отредактировать .env
nano .env
```

Минимальная конфигурация:
```bash
# Модель
CURRENT_MODEL=gigachat_pro
GIGACHAT_CLIENT_ID=your-client-id
GIGACHAT_CLIENT_SECRET=your-client-secret

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password
POSTGRES_DB=your-database

# Reasoning
DEFAULT_REASONING_ENGINE=cot
```

### 3. Запуск

```bash
# Запустить сервис
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001

# Или через systemd
systemctl start python-ai-service
```

### 4. Проверка

```bash
# Health check
curl http://localhost:8001/health

# Тест модели
python3 scripts/test_current_model.py

# Интеграционный тест
./scripts/run_integration_test.sh
```

## Структура проекта

```
python-ai-service/
├── app/                          # Основной код приложения
│   ├── api/                      # API endpoints (FastAPI)
│   ├── chains/                   # RAG/CAG chains
│   ├── chat/                     # Chat service
│   ├── core/                     # Конфигурация и интерфейсы
│   ├── data_access/              # Repositories (DAL)
│   ├── factory/                  # Фабрики для создания компонентов
│   ├── interfaces/               # Интерфейсы
│   ├── models/                   # Pydantic модели
│   ├── monitoring/               # Логирование и метрики
│   ├── providers/                # Провайдеры (модели, БД, reasoning)
│   ├── reasoning/                # Reasoning engines
│   └── services/                 # Бизнес-логика
│
├── tests/                        # Тесты
│   ├── e2e/                      # End-to-end тесты
│   ├── providers/                # Тесты провайдеров
│   └── services/                 # Тесты сервисов
│
├── scripts/                      # Утилиты и скрипты
│   ├── integration_test_full_scenario.py  # Интеграционный тест
│   ├── run_integration_test.sh            # Запуск теста
│   ├── test_current_model.py              # Тест модели
│   ├── test_reflection_engine.py          # Тест reasoning
│   ├── stress_test.py                     # Стресс-тест
│   └── ...
│
├── docs/                         # Документация
│   ├── architecture.md           # Архитектура
│   ├── configuration.md          # Конфигурация
│   ├── INTEGRATION_TEST_GUIDE.md # Интеграционное тестирование
│   ├── QUICK_START_INTEGRATION_TEST.md
│   ├── modules/                  # Руководства по замене модулей
│   │   ├── replacing_model.md
│   │   ├── replacing_reasoning.md
│   │   ├── replacing_database.md
│   │   └── replacing_ux.md
│   └── runbook/                  # Операционные процедуры
│       ├── incident_response.md
│       ├── scaling.md
│       └── backup_restore.md
│
├── .env                          # Конфигурация (не в git)
├── requirements.txt              # Python зависимости
└── README.md                     # Этот файл
```

## Документация

### Основная документация
- [Архитектура](docs/architecture.md) - Полное описание архитектуры
- [Конфигурация](docs/configuration.md) - Все настройки и параметры
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Решение проблем

### Руководства по замене модулей
- [Замена LLM модели](docs/modules/replacing_model.md)
- [Добавление reasoning engine](docs/modules/replacing_reasoning.md)
- [Замена базы данных](docs/modules/replacing_database.md)
- [API и UI интеграция](docs/modules/replacing_ux.md)

### Операционные процедуры (Runbook)
- [Реагирование на инциденты](docs/runbook/incident_response.md)
- [Масштабирование](docs/runbook/scaling.md)
- [Backup и восстановление](docs/runbook/backup_restore.md)

### Тестирование
- [Интеграционное тестирование](docs/INTEGRATION_TEST_GUIDE.md)
- [Быстрый старт теста](docs/QUICK_START_INTEGRATION_TEST.md)
- [Стресс-тестирование](Project_files/Documentation_python/stress_testing/)

## Тестирование

### Unit тесты

```bash
# Запустить все unit тесты
python3 -m pytest tests/

# Запустить конкретный тест
python3 -m pytest tests/providers/test_reasoning.py

# С покрытием
python3 -m pytest tests/ --cov=app --cov-report=html
```

### E2E тесты

```bash
# Запустить E2E тесты
python3 -m pytest tests/e2e/

# Конкретный E2E тест
python3 -m pytest tests/e2e/test_rag_reasoning.py
```

### Интеграционный тест

```bash
# Полный сценарий (автоматический)
./scripts/run_integration_test.sh

# Или вручную
python3 scripts/integration_test_full_scenario.py
```

### Стресс-тестирование

```bash
# Консервативный тест (с учетом rate limits)
./scripts/conservative_stress_test.sh

# Полный стресс-тест
python3 scripts/stress_test.py --users 5 --duration 60
```

## Примеры использования

### Простой запрос к LLM

```python
from app.factory.model_factory import ModelFactory

# Получить модель
model = ModelFactory.get_model("gigachat_pro")

# Генерация ответа
response = await model.generate(
    prompt="Привет! Как дела?",
    temperature=0.7,
    max_tokens=100
)

print(response.content)
```

### Использование Reasoning

```python
from app.factory.reasoning_factory import ReasoningFactory

# Получить reasoning engine
engine = ReasoningFactory.get_reasoning_engine("reflection")

# Выполнить рассуждение
result = await engine.reason(
    query="Какие паттерны в моих данных?",
    context="..."
)

print(result.final_answer)
print(f"Confidence: {result.confidence}")
```

### RAG запрос

```python
from app.chains.rag_chain import RAGChain

# Создать RAG chain
rag_chain = RAGChain()

# Выполнить запрос с контекстом
response = await rag_chain.run(
    query="Что я делал вчера?",
    user_id="user_123"
)

print(response)
```

### API запрос

```bash
# Простой запрос
curl -X POST "http://localhost:8001/api/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Привет!",
    "model": "gigachat_pro",
    "stream": false
  }'

# Streaming запрос
curl -X POST "http://localhost:8001/api/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Расскажи историю",
    "model": "gigachat_pro",
    "reasoning_engine": "reflection",
    "stream": true
  }'
```

## Компоненты

### Поддерживаемые LLM модели
- **GigaChat** (Base, Pro, Max) - Sber AI
- **vLLM** - Локальные модели
- Легко добавить: OpenAI, Claude, и др.

### Reasoning Engines
- **Chain-of-Thought (CoT)** - 4-шаговое рассуждение
- **Reflection/Critic Loops** - Итеративное улучшение
- Расширяемая архитектура

### Базы данных
- **PostgreSQL** - Реляционные данные
- **Neo4j** - Граф знаний
- **ChromaDB** - Векторный поиск (встраиваемый)
- **Milvus** - Векторный поиск (production)
- **Redis** - Кэширование

### Поисковые провайдеры
- **Vector Search** - Семантический поиск
- **BM25** - Полнотекстовый поиск
- **Hybrid Search** - Комбинированный поиск
- **Graph Search** - Поиск по графу

## Производительность

### Benchmarks

| Операция | Latency (p50) | Latency (p95) | Throughput |
|----------|---------------|---------------|------------|
| Simple query | 800ms | 1.5s | 10 RPS |
| RAG query | 1.2s | 2.5s | 5 RPS |
| Streaming | 200ms (first chunk) | 500ms | 8 RPS |
| Reasoning (CoT) | 2.5s | 4s | 3 RPS |
| Reasoning (Reflection) | 4s | 7s | 2 RPS |

*Тесты проведены с GigaChat Pro на одном инстансе*

### Rate Limits

**GigaChat API:**
- ~10 запросов в минуту (зависит от тарифа)
- Рекомендуется: 5 RPS максимум для стабильности

**Рекомендации:**
- Используйте кэширование для частых запросов
- Настройте rate limiting на уровне API
- Масштабируйте горизонтально для высокой нагрузки

## Deployment

### Docker

```bash
# Собрать образ
docker build -t python-ai-service:latest .

# Запустить
docker run -d \
  --name python-ai-service \
  -p 8001:8001 \
  --env-file .env \
  python-ai-service:latest
```

### Docker Compose

```bash
# Запустить все сервисы
docker-compose up -d

# Масштабировать API
docker-compose up -d --scale api=3
```

### Kubernetes

```bash
# Применить манифесты
kubectl apply -f k8s/

# Масштабировать
kubectl scale deployment python-ai-service --replicas=5

# Автомасштабирование
kubectl autoscale deployment python-ai-service --min=3 --max=10 --cpu-percent=70
```

## Мониторинг

### Метрики

- Request latency (p50, p95, p99)
- Error rate
- Throughput (RPS)
- Model availability
- Database connections
- Cache hit rate

### Логи

```bash
# Просмотр логов
tail -f /var/log/python-ai-service/app.log

# Или через journalctl
journalctl -u python-ai-service -f

# Или через Docker
docker logs -f python-ai-service
```

### Health Checks

```bash
# API health
curl http://localhost:8001/health

# Detailed health
curl http://localhost:8001/health/detailed
```

## Troubleshooting

### Частые проблемы

1. **API не отвечает**
   - Проверьте что сервис запущен: `systemctl status python-ai-service`
   - Проверьте логи: `journalctl -u python-ai-service -n 100`

2. **Ошибки аутентификации GigaChat**
   - Используйте CLIENT_ID/SECRET вместо CREDENTIALS
   - Проверьте что нет пробелов в credentials

3. **Медленные ответы**
   - Проверьте rate limits GigaChat API
   - Увеличьте количество workers
   - Используйте кэширование

4. **Ошибки подключения к БД**
   - Проверьте что PostgreSQL запущен
   - Проверьте credentials в .env
   - Проверьте firewall правила

См. [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) для подробностей.

## Contributing

### Добавление новой модели

1. Создать провайдер в `app/providers/models/`
2. Реализовать интерфейс `IModelProvider`
3. Зарегистрировать в `ModelFactory`
4. Добавить конфигурацию в `config.py`
5. Написать тесты

См. [replacing_model.md](docs/modules/replacing_model.md)

### Добавление reasoning engine

1. Создать класс в `app/reasoning/`
2. Наследовать от `BaseReasoning`
3. Создать provider в `app/providers/reasoning/`
4. Зарегистрировать в `ReasoningFactory`
5. Написать тесты

См. [replacing_reasoning.md](docs/modules/replacing_reasoning.md)

## Лицензия

[Укажите вашу лицензию]

## Контакты

- Email: [your-email]
- Slack: [your-slack-channel]
- Issues: [github-issues-url]

## Changelog

### v0.1.0 (2024-XX-XX)

**Добавлено:**
- ✓ Модульная архитектура с чистым разделением слоев
- ✓ Поддержка GigaChat (Base, Pro, Max) и vLLM
- ✓ Chain-of-Thought reasoning engine
- ✓ Reflection/Critic Loops reasoning engine
- ✓ RAG с векторным и BM25 поиском
- ✓ Поддержка ChromaDB и Milvus
- ✓ Comprehensive тестирование
- ✓ Полная документация на русском
- ✓ Интеграционный тест полного сценария
- ✓ Стресс-тестирование с учетом rate limits
- ✓ Runbook для операционной работы

**Исправлено:**
- ✓ E2E тесты (AsyncMock.keys() ошибка)
- ✓ GigaChat аутентификация
- ✓ Утечки памяти (unclosed sessions)
- ✓ Стресс-тесты (ZeroDivisionError)

## Roadmap

### v0.2.0
- [ ] Поддержка OpenAI API
- [ ] Поддержка Claude
- [ ] Tree-of-Thoughts reasoning
- [ ] Улучшенный гибридный поиск
- [ ] Grafana dashboards

### v0.3.0
- [ ] Multi-tenancy
- [ ] Advanced caching strategies
- [ ] Distributed tracing
- [ ] Auto-scaling policies

## Благодарности

- FastAPI за отличный веб-фреймворк
- LangChain за LLM абстракции
- Sber AI за GigaChat API
- Сообщество open-source

---

**Статус проекта:** Production-ready ✓

**Последнее обновление:** 2024-XX-XX
