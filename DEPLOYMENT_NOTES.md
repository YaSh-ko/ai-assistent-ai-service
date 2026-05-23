# Deployment Notes - Rate Limit Fix

## Изменения
Исправлена обработка ошибок 429 (Too Many Requests) от GigaChat API.

## Новые файлы
- `app/utils/rate_limiter.py` - адаптивный rate limiter
- `tests/utils/test_rate_limiter.py` - тесты
- `RATE_LIMIT_FIX.md` - подробная документация

## Измененные файлы
- `app/providers/models/gigachat_provider.py` - улучшенный retry с jitter и rate limiting
- `app/services/embedding_service.py` - улучшенный retry с jitter

## Требования
Нет новых зависимостей - используются только стандартные библиотеки Python.

## Тестирование
```bash
# Запуск тестов rate limiter
pytest tests/utils/test_rate_limiter.py -v

# Запуск всех тестов
pytest tests/ -v
```

## Мониторинг после деплоя

### Что проверить:
1. **Логи 429 ошибок** - должны уменьшиться
2. **Retry попытки** - должны быть с jitter (разные задержки)
3. **Circuit breaker** - не должен активироваться часто
4. **Latency** - может немного увеличиться из-за задержек

### Ключевые метрики:
```
# Количество 429 ошибок
grep "429 от GigaChat" logs/app.log | wc -l

# Активации circuit breaker
grep "Circuit breaker активирован" logs/app.log | wc -l

# Успешные запросы после retry
grep "GigaChat response:" logs/app.log | wc -l
```

## Rollback план
Если возникнут проблемы:
1. Откатить изменения в `gigachat_provider.py` и `embedding_service.py`
2. Удалить `rate_limiter.py` (не используется другими модулями)
3. Перезапустить сервис

## Настройка (опционально)

### Изменение задержек retry:
В `gigachat_provider.py` и `embedding_service.py`:
```python
_RETRY_DELAYS = [1.0, 2.0, 4.0, 8.0]  # Можно изменить
```

### Настройка rate limiter:
В `gigachat_provider.py`, метод `__init__`:
```python
self._rate_limiter = AdaptiveRateLimiter(
    initial_delay=0.0,  # Начальная задержка
    max_delay=10.0      # Максимальная задержка
)
```

### Настройка circuit breaker:
В `rate_limiter.py`, метод `should_circuit_break`:
```python
if self._consecutive_429s >= 5:  # Порог активации
    if time_since_last_429 < 60:  # Временное окно
```

## Ожидаемые результаты
- ✅ Меньше ошибок 429 в логах
- ✅ Автоматическое восстановление после rate limit
- ✅ Нет "thundering herd" эффекта
- ✅ Правильная обработка streaming запросов
- ⚠️ Небольшое увеличение latency (из-за адаптивных задержек)

## Контакты
При возникновении проблем проверьте:
1. Логи приложения
2. Метрики GigaChat API
3. Документацию в `RATE_LIMIT_FIX.md`
