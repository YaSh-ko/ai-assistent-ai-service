# Python AI Service (Impulse)

Интеллектуальный ассистент: RAG, гибридный поиск, граф знаний (Neo4j), детектор сущностей (event / goal / experiment).

## Запуск локально

```bash
cp .env.example .env.local
docker compose --env-file .env.local -f docker-compose.dev.yml up -d
```

Подробнее: [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md)

## API

- LangGraph SDK: `/api/v1/threads`, `/api/v1/runs/stream`
- Детектор: `/api/v1/detector/*`
- Документация: http://localhost:8000/docs

## Тесты

```bash
pytest tests/services/test_detector_session_service.py tests/services/test_detector_service_proposal.py -q
```
