# Локальная разработка (только Docker на машине)

Продовые хосты и staging-compose **не используются**. Все БД — контейнеры на `localhost`.

## Какие файлы Docker есть и зачем

| Файл | Оставить? | Назначение |
|------|-----------|------------|
| **`docker-compose.dev.yml`** | ✅ основной | Полный стек: Postgres + Neo4j + Redis + Chroma + **ai-service** |
| **`docker-compose.yml`** | ✅ опционально | Только инфраструктура (БД без ai-service), если API/AI запускаешь в IDE |
| **`Dockerfile`** | ✅ | Сборка образа ai-service |
| ~~`docker-compose.staging.yml`~~ | ❌ удалён | Был для удалённого staging/мониторинга |
| ~~`docker-compose.local.yml`~~ | ❌ удалён | Устаревший (один Postgres на 5432) |

### Репозиторий `api/`

| Файл | Оставить? | Назначение |
|------|-----------|------------|
| **`Dockerfile`** | ✅ | Сборка API (обычно **не** в Docker, а `uvicorn` в IDE) |
| ~~`docker-compose.staging.yml`~~ | ❌ удалён | Staging API в external-сети GitLab |

### `local-dev-env/` (корень монорепо)

| Файл | Оставить? | Назначение |
|------|-----------|------------|
| **`docker-compose.local.yml`** | ✅ альтернатива | API + AI + все БД одной командой (удобно для «всё в Docker») |

## Быстрый старт (рекомендуется)

### 1. Env

```bash
cp .env.example .env.local
# Отредактируй пароли в .env.local (один NEO4J_PASSWORD для Neo4j и клиентов)
```

В **`api/`** то же: `cp .env.example .env` — только `localhost` / `host.docker.internal`, пользователь Neo4j **`neo4j`**.

### 2. Поднять стек

```bash
cd python-ai-service
docker compose --env-file .env.local -f docker-compose.dev.yml up -d
```

- Postgres: `localhost:5433`
- Neo4j Browser: http://localhost:7474 (`neo4j` + пароль из `.env.local`)
- AI: http://localhost:8000

### 3. API на хосте (PyCharm / терминал)

В `api/.env`:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
```

Если API в Docker (`local-dev-env`) — хосты `db` / `neo4j` задаёт compose, не `.env`.

### 4. Миграции Postgres

```bash
cd api
# подгрузить .env, проверить DATABASE_URL → localhost:5433/db_for_delez
alembic -c common/database/migrations/postgresql/... upgrade head
```

## Два режима

```text
Режим A — ai-only в Docker, API в IDE
  docker-compose.dev.yml  →  БД + AI
  api: uvicorn на хосте    →  localhost:5433, localhost:7687

Режим B — только БД в Docker
  docker compose --env-file .env.local up -d   # docker-compose.yml
  api + ai-service в IDE

Режим C — всё в Docker
  cd local-dev-env && docker compose -f docker-compose.local.yml up -d
```

## Защита от прод

- В `api` при старте: если в URL есть `delez-repo.ru`, `85.198.103.254` и т.п. — **падение** (см. `config.py`).
- Не храни прод-секреты в `.env` / `.env.local` (файлы в `.gitignore`).

## Порты (не путать)

| Сервис | Порт на хосте |
|--------|----------------|
| Postgres | 5433 |
| Neo4j Bolt | 7687 |
| Neo4j UI | 7474 |
| AI service | 8000 |
| Chroma (dev.yml) | 8002 |
| Chroma (docker-compose.yml) | 8001 |
| API (local-dev-env) | 8001 |
