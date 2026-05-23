# Руководство по реагированию на инциденты

## Обзор

Данное руководство описывает процедуры реагирования на инциденты в Python AI Service. Включает диагностику проблем, шаги по восстановлению и эскалацию.

## Классификация инцидентов

### Severity Levels

**P0 - Critical (Критический)**
- Полный отказ сервиса
- Потеря данных
- Нарушение безопасности
- SLA: Реагирование немедленно, восстановление < 1 час

**P1 - High (Высокий)**
- Частичный отказ сервиса
- Значительное снижение производительности
- Проблемы с ключевыми функциями
- SLA: Реагирование < 15 минут, восстановление < 4 часа

**P2 - Medium (Средний)**
- Незначительные проблемы с функциональностью
- Умеренное снижение производительности
- Проблемы с некритичными функциями
- SLA: Реагирование < 1 час, восстановление < 24 часа

**P3 - Low (Низкий)**
- Косметические проблемы
- Минимальное влияние на пользователей
- SLA: Реагирование < 24 часа, восстановление < 1 неделя

## Общий процесс реагирования

### 1. Обнаружение

**Источники:**
- Мониторинг (Prometheus, Grafana)
- Алерты (PagerDuty, Slack)
- Пользовательские жалобы
- Логи

**Действия:**
1. Подтвердить инцидент
2. Определить severity
3. Создать тикет
4. Уведомить команду

### 2. Диагностика

**Шаги:**
1. Проверить статус сервисов
2. Проверить логи
3. Проверить метрики
4. Проверить зависимости

**Инструменты:**
```bash
# Проверка статуса сервиса
systemctl status python-ai-service

# Проверка логов
journalctl -u python-ai-service -n 100 --no-pager

# Проверка процессов
ps aux | grep uvicorn

# Проверка портов
netstat -tulpn | grep 8001

# Проверка ресурсов
top
df -h
free -m
```

### 3. Восстановление

**Приоритеты:**
1. Восстановить сервис
2. Минимизировать потерю данных
3. Сохранить доказательства для анализа

### 4. Коммуникация

**Кому сообщать:**
- Команда разработки
- Менеджмент
- Пользователи (при необходимости)

**Что сообщать:**
- Описание проблемы
- Влияние на пользователей
- Статус восстановления
- ETA восстановления

### 5. Post-Mortem

**После восстановления:**
1. Написать отчет о инциденте
2. Провести анализ первопричины (RCA)
3. Определить action items
4. Обновить runbook

## Типичные инциденты

### Инцидент 1: Сервис не отвечает

**Симптомы:**
- HTTP 502/503 ошибки
- Таймауты запросов
- Health check fails

**Диагностика:**
```bash
# 1. Проверить статус сервиса
systemctl status python-ai-service

# 2. Проверить логи
tail -f /var/log/python-ai-service/error.log

# 3. Проверить процессы
ps aux | grep uvicorn

# 4. Проверить порты
netstat -tulpn | grep 8001
```

**Возможные причины:**
- Процесс упал
- Порт занят
- Нехватка ресурсов
- Проблемы с зависимостями

**Восстановление:**

**Вариант 1: Перезапуск сервиса**
```bash
# Остановить сервис
systemctl stop python-ai-service

# Проверить что процесс завершен
ps aux | grep uvicorn

# Если процесс висит, убить принудительно
pkill -9 uvicorn

# Запустить сервис
systemctl start python-ai-service

# Проверить статус
systemctl status python-ai-service

# Проверить логи
journalctl -u python-ai-service -f
```

**Вариант 2: Проблема с портом**
```bash
# Найти процесс на порту 8001
lsof -i :8001

# Убить процесс
kill -9 <PID>

# Запустить сервис
systemctl start python-ai-service
```

**Вариант 3: Нехватка ресурсов**
```bash
# Проверить память
free -m

# Проверить диск
df -h

# Очистить логи если нужно
journalctl --vacuum-time=7d

# Перезапустить сервис
systemctl restart python-ai-service
```

### Инцидент 2: Медленные ответы

**Симптомы:**
- Высокая latency (> 5 секунд)
- Таймауты
- Очереди запросов

**Диагностика:**
```bash
# 1. Проверить метрики
curl http://localhost:8001/metrics

# 2. Проверить нагрузку
top
htop

# 3. Проверить соединения
netstat -an | grep 8001 | wc -l

# 4. Проверить логи
grep "slow" /var/log/python-ai-service/app.log
```

**Возможные причины:**
- Высокая нагрузка
- Медленные запросы к БД
- Медленные запросы к LLM API
- Утечки памяти
- Блокировки

**Восстановление:**

**Вариант 1: Масштабирование**
```bash
# Запустить дополнительные инстансы
docker-compose up -d --scale api=3

# Или через systemd
systemctl start python-ai-service@2
systemctl start python-ai-service@3
```

**Вариант 2: Оптимизация**
```bash
# Очистить кэш
redis-cli FLUSHALL

# Перезапустить с увеличенными ресурсами
# Отредактировать /etc/systemd/system/python-ai-service.service
# Добавить:
# Environment="WORKERS=4"
# Environment="WORKER_CLASS=uvicorn.workers.UvicornWorker"

systemctl daemon-reload
systemctl restart python-ai-service
```

**Вариант 3: Rate Limiting**
```python
# Временно включить агрессивный rate limiting
# В .env:
RATE_LIMIT_PER_MINUTE=10

# Перезапустить
systemctl restart python-ai-service
```

### Инцидент 3: Ошибки подключения к БД

**Симптомы:**
- "Connection refused" ошибки
- "Too many connections"
- "Connection timeout"

**Диагностика:**
```bash
# 1. Проверить PostgreSQL
systemctl status postgresql

# 2. Проверить соединения
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity;"

# 3. Проверить логи PostgreSQL
tail -f /var/log/postgresql/postgresql-15-main.log

# 4. Проверить Neo4j
systemctl status neo4j
curl http://localhost:7474
```

**Возможные причины:**
- БД недоступна
- Превышен лимит соединений
- Сетевые проблемы
- Неверные credentials

**Восстановление:**

**Вариант 1: Перезапуск БД**
```bash
# PostgreSQL
systemctl restart postgresql

# Neo4j
systemctl restart neo4j

# Проверить статус
systemctl status postgresql
systemctl status neo4j
```

**Вариант 2: Увеличение лимита соединений**
```bash
# PostgreSQL
sudo -u postgres psql

# В psql:
ALTER SYSTEM SET max_connections = 200;
SELECT pg_reload_conf();

# Или отредактировать /etc/postgresql/15/main/postgresql.conf
# max_connections = 200

# Перезапустить
systemctl restart postgresql
```

**Вариант 3: Закрытие idle соединений**
```bash
# PostgreSQL
sudo -u postgres psql -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
AND state_change < current_timestamp - INTERVAL '5 minutes';
"
```

### Инцидент 4: Ошибки LLM API

**Симптомы:**
- "Model unavailable"
- "Rate limit exceeded"
- "Authentication failed"

**Диагностика:**
```bash
# 1. Проверить доступность API
curl https://gigachat.devices.sberbank.ru/api/v1/health

# 2. Проверить credentials
cat .env | grep GIGACHAT

# 3. Проверить логи
grep "GigaChat" /var/log/python-ai-service/app.log

# 4. Тест модели
python3 scripts/test_current_model.py
```

**Возможные причины:**
- API недоступен
- Неверные credentials
- Rate limit
- Истек токен

**Восстановление:**

**Вариант 1: Переключение на fallback модель**
```bash
# В .env изменить:
CURRENT_MODEL=gigachat  # вместо gigachat_pro

# Перезапустить
systemctl restart python-ai-service
```

**Вариант 2: Обновление credentials**
```bash
# Обновить .env
nano .env

# Изменить:
GIGACHAT_CLIENT_ID=new-client-id
GIGACHAT_CLIENT_SECRET=new-client-secret

# Перезапустить
systemctl restart python-ai-service
```

**Вариант 3: Rate limit - ожидание**
```bash
# Временно отключить сервис
systemctl stop python-ai-service

# Подождать 5-10 минут

# Запустить с пониженной нагрузкой
# В .env:
RATE_LIMIT_PER_MINUTE=5

systemctl start python-ai-service
```

### Инцидент 5: Утечка памяти

**Симптомы:**
- Постоянный рост использования памяти
- OOM (Out of Memory) ошибки
- Процесс убивается системой

**Диагностика:**
```bash
# 1. Проверить использование памяти
free -m
ps aux --sort=-%mem | head

# 2. Мониторинг в реальном времени
watch -n 1 'ps aux | grep uvicorn'

# 3. Проверить логи на OOM
dmesg | grep -i "out of memory"

# 4. Memory profiling (если возможно)
python3 -m memory_profiler app/main.py
```

**Возможные причины:**
- Утечка в коде
- Большие объекты в памяти
- Кэш не очищается
- Слишком много workers

**Восстановление:**

**Вариант 1: Перезапуск**
```bash
# Немедленный перезапуск
systemctl restart python-ai-service

# Настроить автоматический перезапуск
# В /etc/systemd/system/python-ai-service.service:
[Service]
Restart=always
RestartSec=10
```

**Вариант 2: Уменьшение workers**
```bash
# В .env:
WORKERS=2  # вместо 4

systemctl restart python-ai-service
```

**Вариант 3: Очистка кэша**
```bash
# Redis
redis-cli FLUSHALL

# Перезапуск
systemctl restart python-ai-service
```

**Вариант 4: Ограничение памяти**
```bash
# В /etc/systemd/system/python-ai-service.service:
[Service]
MemoryLimit=2G
MemoryMax=2.5G

systemctl daemon-reload
systemctl restart python-ai-service
```

## Escalation Matrix

### Level 1: On-Call Engineer
- Первичное реагирование
- Базовая диагностика
- Стандартные процедуры восстановления

### Level 2: Senior Engineer
- Сложная диагностика
- Нестандартные проблемы
- Изменения конфигурации

### Level 3: Team Lead / Architect
- Архитектурные проблемы
- Критические решения
- Координация с другими командами

### Level 4: Management
- Бизнес-критические инциденты
- Коммуникация с клиентами
- Ресурсные решения

## Контакты

```
On-Call Engineer: +7-XXX-XXX-XXXX
Senior Engineer: +7-XXX-XXX-XXXX
Team Lead: +7-XXX-XXX-XXXX
Slack Channel: #incidents
PagerDuty: https://yourcompany.pagerduty.com
```

## Инструменты

### Мониторинг
- Grafana: http://monitoring.example.com:3000
- Prometheus: http://monitoring.example.com:9090
- Logs: http://logs.example.com

### Управление
- Kubernetes Dashboard: http://k8s.example.com
- Docker Registry: http://registry.example.com
- CI/CD: http://ci.example.com

## Чеклист реагирования

### Немедленные действия
- [ ] Подтвердить инцидент
- [ ] Определить severity
- [ ] Создать тикет
- [ ] Уведомить команду
- [ ] Начать диагностику

### Во время инцидента
- [ ] Регулярные обновления статуса (каждые 15-30 минут)
- [ ] Документировать все действия
- [ ] Сохранять логи и метрики
- [ ] Координация с другими командами

### После восстановления
- [ ] Подтвердить восстановление
- [ ] Уведомить заинтересованные стороны
- [ ] Написать incident report
- [ ] Запланировать post-mortem
- [ ] Обновить документацию

## Post-Mortem Template

```markdown
# Incident Report: [Краткое описание]

## Metadata
- Date: YYYY-MM-DD
- Duration: X hours
- Severity: P0/P1/P2/P3
- Affected Users: X%
- Incident Lead: [Имя]

## Summary
[Краткое описание инцидента]

## Timeline
- HH:MM - Инцидент обнаружен
- HH:MM - Начата диагностика
- HH:MM - Причина определена
- HH:MM - Восстановление начато
- HH:MM - Сервис восстановлен

## Root Cause
[Детальное описание первопричины]

## Impact
- Users affected: X
- Revenue impact: $X
- Downtime: X hours

## Resolution
[Описание как проблема была решена]

## Action Items
1. [ ] [Действие 1] - Owner: [Имя] - Due: [Дата]
2. [ ] [Действие 2] - Owner: [Имя] - Due: [Дата]

## Lessons Learned
- What went well
- What could be improved
- What we learned
```

## Ссылки

- [Architecture](../architecture.md)
- [Monitoring Guide](./monitoring.md)
- [Scaling Guide](./scaling.md)
- [Backup & Restore](./backup_restore.md)
