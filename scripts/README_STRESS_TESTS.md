# Stress Testing Guide

Руководство по проведению нагрузочного тестирования AI сервиса.

## Установка зависимостей

```bash
pip install httpx
```

## Быстрый старт

### 1. Запуск одиночного теста

```bash
# Простой тест с 10 пользователями на 60 секунд
python scripts/stress_test.py --users 10 --duration 60 --type simple

# RAG тест с целевым RPS
python scripts/stress_test.py --users 50 --duration 30 --rps 50 --type rag

# Reasoning тест
python scripts/stress_test.py --users 20 --duration 30 --rps 10 --type reasoning

# Streaming тест
python scripts/stress_test.py --users 50 --duration 30 --rps 50 --type streaming
```

### 2. Запуск полного набора тестов

```bash
# Запустить все тесты с разными конфигурациями
python scripts/stress_test.py --suite
```

Это запустит:
- Simple requests: 10, 50, 100 RPS
- RAG requests: 10, 50 RPS
- Reasoning requests: 5, 10 RPS
- Streaming requests: 10, 50 RPS

### 3. Анализ результатов

```bash
# Сгенерировать отчет из результатов
python scripts/analyze_stress_results.py --results-dir stress_test_results --output docs/performance_report.md
```

## Параметры командной строки

### stress_test.py

```
--url URL              Base URL сервиса (default: http://localhost:8000)
--users N              Количество параллельных пользователей (default: 10)
--duration N           Длительность теста в секундах (default: 60)
--rps N                Целевой RPS (requests per second)
--type TYPE            Тип теста: simple, rag, reasoning, streaming
--suite                Запустить полный набор тестов
--output FILE          Сохранить результаты в JSON файл
```

### analyze_stress_results.py

```
--results-dir DIR      Директория с результатами (default: stress_test_results)
--output FILE          Выходной markdown файл (default: docs/performance_report.md)
```

## Типы тестов

### Simple
Простые запросы без RAG и reasoning:
- Запрос: "Привет!"
- Ожидаемая latency: ~500ms
- Рекомендуемый RPS: до 100

### RAG
Запросы с поиском по базе знаний:
- Запрос: "Что я писал вчера про философию?"
- Ожидаемая latency: ~1500ms
- Рекомендуемый RPS: до 50

### Reasoning
Сложные запросы с CoT reasoning:
- Запрос: "Проанализируй мои последние записи и найди связи между концепциями."
- Ожидаемая latency: ~5000ms
- Рекомендуемый RPS: до 10

### Streaming
Streaming запросы через SSE:
- Запрос: "Расскажи длинную историю."
- Метрики: TTFB, общая latency
- Рекомендуемый RPS: до 50

## Метрики

### Throughput
- **Actual RPS**: Фактическое количество запросов в секунду
- **Target Efficiency**: Процент достижения целевого RPS

### Latency
- **Average**: Средняя задержка
- **p50**: Медиана (50-й перцентиль)
- **p95**: 95-й перцентиль
- **p99**: 99-й перцентиль

### Error Rate
- Процент неуспешных запросов (не 2xx статус или exception)

### TTFB (Time to First Byte)
Только для streaming запросов:
- Время до получения первого chunk'а данных

## Интерпретация результатов

### Хорошие показатели

**Simple requests (10 RPS):**
- Latency p95: < 1000ms
- Error rate: < 1%
- Throughput: ~10 RPS

**RAG requests (10 RPS):**
- Latency p95: < 2000ms
- Error rate: < 2%
- Throughput: ~10 RPS

**Reasoning requests (5 RPS):**
- Latency p95: < 8000ms
- Error rate: < 5%
- Throughput: ~5 RPS

**Streaming requests (10 RPS):**
- TTFB p95: < 1000ms
- Total latency p95: < 5000ms
- Error rate: < 1%

### Признаки проблем

1. **Высокая latency (p95 > p50 * 3)**
   - Возможная причина: Неравномерная нагрузка, GC паузы
   - Решение: Профилирование, оптимизация горячих путей

2. **Низкий throughput (< 80% от target)**
   - Возможная причина: Bottleneck в БД или LLM API
   - Решение: Масштабирование, кэширование

3. **Высокий error rate (> 5%)**
   - Возможная причина: Таймауты, ошибки подключения
   - Решение: Увеличение таймаутов, retry логика

4. **Растущая latency с нагрузкой**
   - Возможная причина: Недостаточно ресурсов
   - Решение: Вертикальное или горизонтальное масштабирование

## Рекомендации по конфигурации

### Низкая нагрузка (< 20 RPS)
```python
# config.py
GIGACHAT_MODEL = "GigaChat"  # base
ENABLE_COT_REASONING = True
ENABLE_COT_VERIFICATION = True
USE_NEO4J_GRAPH = True
```

### Средняя нагрузка (20-50 RPS)
```python
GIGACHAT_MODEL = "GigaChat-Pro"
ENABLE_COT_REASONING = True
ENABLE_COT_VERIFICATION = False  # Отключить verification
USE_NEO4J_GRAPH = True
ENABLE_CACHING = True
```

### Высокая нагрузка (> 50 RPS)
```python
GIGACHAT_MODEL = "GigaChat"  # Вернуться к base для скорости
ENABLE_COT_REASONING = False  # Отключить для простых запросов
USE_NEO4J_GRAPH = False  # Только PostgreSQL
ENABLE_CACHING = True
CACHE_TTL = 3600
```

## Примеры использования

### Тест базовой нагрузки (10 RPS)

```bash
python scripts/stress_test.py \
  --users 10 \
  --duration 60 \
  --rps 10 \
  --type simple \
  --output results/baseline_10rps.json
```

### Тест средней нагрузки (50 RPS)

```bash
python scripts/stress_test.py \
  --users 50 \
  --duration 60 \
  --rps 50 \
  --type rag \
  --output results/medium_50rps.json
```

### Тест пиковой нагрузки (100 RPS)

```bash
python scripts/stress_test.py \
  --users 100 \
  --duration 30 \
  --rps 100 \
  --type simple \
  --output results/peak_100rps.json
```

### Полный набор тестов с анализом

```bash
# 1. Запустить все тесты
python scripts/stress_test.py --suite

# 2. Сгенерировать отчет
python scripts/analyze_stress_results.py

# 3. Просмотреть отчет
cat docs/performance_report.md
```

## Troubleshooting

### Ошибка: Connection refused
```
Решение: Убедитесь, что сервис запущен на указанном URL
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Ошибка: Too many open files
```
Решение: Увеличьте лимит файловых дескрипторов
ulimit -n 10000
```

### Высокий error rate
```
Решение: 
1. Проверьте логи сервиса
2. Уменьшите RPS target
3. Увеличьте timeout в stress_test.py
```

### Низкий throughput
```
Решение:
1. Проверьте CPU/Memory usage
2. Оптимизируйте медленные запросы
3. Добавьте кэширование
4. Масштабируйте сервис
```

## Continuous Performance Testing

### GitHub Actions Integration

Создайте `.github/workflows/performance.yml`:

```yaml
name: Performance Tests

on:
  schedule:
    - cron: '0 2 * * *'  # Каждую ночь в 2:00
  workflow_dispatch:

jobs:
  performance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install httpx
      
      - name: Start service
        run: |
          python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
          sleep 10
      
      - name: Run stress tests
        run: python scripts/stress_test.py --suite
      
      - name: Generate report
        run: python scripts/analyze_stress_results.py
      
      - name: Upload results
        uses: actions/upload-artifact@v2
        with:
          name: performance-results
          path: |
            stress_test_results/
            docs/performance_report.md
```

## Дополнительные ресурсы

- [Документация по архитектуре](../Project_files/Documentation_python/Architecture.md)
- [API документация](../Project_files/Documentation_python/API.md)
- [Руководство по оптимизации](../Project_files/Documentation_python/optimization_guide.md)
