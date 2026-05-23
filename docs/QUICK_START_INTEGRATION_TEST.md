# Быстрый старт - Интеграционный тест

## Запуск за 3 шага

### 1. Убедитесь что .env настроен

```bash
# Проверьте наличие обязательных переменных
cat .env | grep -E "GIGACHAT_CLIENT_ID|POSTGRES_HOST|CURRENT_MODEL"
```

Минимальные требования:
- `GIGACHAT_CLIENT_ID` и `GIGACHAT_CLIENT_SECRET`
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `CURRENT_MODEL=gigachat_pro`

### 2. Запустите тест

```bash
# Автоматический запуск (рекомендуется)
./scripts/run_integration_test.sh
```

Скрипт автоматически:
- ✓ Проверит зависимости
- ✓ Запустит сервис если нужно
- ✓ Выполнит все 7 шагов теста
- ✓ Остановит сервис после теста

### 3. Проверьте результат

Успешный результат:
```
======================================================================
✓ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!
======================================================================
```

## Что тестируется

1. ✓ Создание сеанса через API
2. ✓ Запись 5 событий в дневник
3. ✓ Синхронизация с Neo4j и ChromaDB
4. ✓ Вопрос о паттернах с RAG
5. ✓ Streaming ответ с reasoning
6. ✓ Сохранение диалога
7. ✓ Восстановление истории

## Альтернативный запуск

### Если сервис уже запущен

```bash
# Запустить только тест (без запуска сервиса)
python3 scripts/integration_test_full_scenario.py http://localhost:8001
```

### С кастомным портом

```bash
# Запустить на порту 8002
./scripts/run_integration_test.sh http://localhost:8002 8002
```

## Troubleshooting

### Ошибка: API недоступен

```bash
# Запустите сервис вручную
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001

# В другом терминале запустите тест
python3 scripts/integration_test_full_scenario.py
```

### Ошибка: PostgreSQL недоступен

```bash
# Проверьте PostgreSQL
systemctl status postgresql
pg_isready -h localhost -p 5433

# Проверьте настройки
cat .env | grep POSTGRES
```

### Ошибка: GigaChat authentication

```bash
# Проверьте credentials
cat .env | grep GIGACHAT

# Убедитесь что используете CLIENT_ID/SECRET, а не CREDENTIALS
# Закомментируйте GIGACHAT_CREDENTIALS если есть
```

## Полная документация

См. [INTEGRATION_TEST_GUIDE.md](./INTEGRATION_TEST_GUIDE.md) для:
- Детального описания каждого шага
- Расширенной конфигурации
- Интеграции в CI/CD
- Метрик и мониторинга
