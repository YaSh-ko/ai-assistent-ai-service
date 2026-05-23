# Test Coverage Improvement Plan

## Overview
This document outlines the test coverage improvement plan based on SonarQube analysis.

## Priority Files for Testing

### High Priority (Core Application Logic)
1. ✅ `app/api/runs.py` - 37.1% → Target: 80%+
2. ✅ `app/api/threads.py` - 40.6% → Target: 80%+
3. `app/core/config.py` - 0.0% → Target: 70%+
4. `app/chains/rag_chain.py` - 71.7% → Target: 85%+
5. `app/reasoning/reflection_reasoning.py` - 31.3% → Target: 75%+
6. `app/providers/embeddings/gigachat_embeddings.py` - 0.0% → Target: 70%+
7. `app/providers/models/gigachat_provider.py` - 58.8% → Target: 80%+
8. `app/providers/databases/chroma_provider.py` - 53.1% → Target: 75%+
9. `app/providers/databases/milvus_provider.py` - 9.5% → Target: 70%+
10. `app/factory/database_factory.py` - 55.6% → Target: 75%+
11. `app/factory/model_factory.py` - 83.3% → Target: 90%+

### Medium Priority (Data Access & Repositories)
12. `app/data_access/postgresql/chat_session_repository.py` - 2.6% → Target: 70%+
13. `app/data_access/postgresql/base_repository.py` - 40.0% → Target: 75%+
14. `app/providers/databases/postgres_provider.py` - 73.5% → Target: 85%+

### Low Priority (Scripts - Integration/Manual Tests)
- Scripts are typically not unit tested as they are integration/manual test scripts
- Focus on application code first

## Test Files Created

### API Tests
- ✅ `tests/api/test_runs.py` - Comprehensive tests for runs API
- ✅ `tests/api/test_threads.py` - Comprehensive tests for threads API

### Core Tests
- `tests/core/test_config_extended.py` - Extended config tests (to be created)

### Provider Tests
- `tests/providers/test_gigachat_embeddings.py` - GigaChat embeddings tests (to be created)
- `tests/providers/test_gigachat_provider_extended.py` - Extended GigaChat provider tests (to be created)
- `tests/providers/test_chroma_provider_extended.py` - Extended ChromaDB tests (to be created)
- `tests/providers/test_milvus_provider_extended.py` - Extended Milvus tests (to be created)

### Chain Tests
- `tests/chains/test_rag_chain_extended.py` - Extended RAG chain tests (to be created)

### Reasoning Tests
- `tests/reasoning/test_reflection_reasoning.py` - Reflection reasoning tests (to be created)

### Factory Tests
- `tests/factory/test_database_factory_extended.py` - Extended database factory tests (to be created)
- `tests/factory/test_model_factory_extended.py` - Extended model factory tests (to be created)

### Repository Tests
- `tests/data_access/test_chat_session_repository.py` - Chat session repository tests (to be created)
- `tests/data_access/test_base_repository_extended.py` - Extended base repository tests (to be created)

## Testing Strategy

### Unit Tests
- Mock external dependencies (databases, APIs, file systems)
- Test individual functions and methods in isolation
- Focus on edge cases and error handling
- Use pytest fixtures for common setup

### Integration Tests
- Test interactions between components
- Use test databases where possible
- Mock only external services (GigaChat API, etc.)

### Mocking Strategy
- **Always Mock**: External APIs (GigaChat, VLLM), File I/O, Network calls
- **Sometimes Mock**: Databases (use test DB for integration, mock for unit)
- **Never Mock**: Internal business logic, data transformations

## Coverage Goals

### Overall Target
- Current: ~40-50% (estimated)
- Target: 75%+ overall coverage
- Critical paths: 85%+ coverage

### Per-File Targets
- API endpoints: 80%+
- Core business logic: 85%+
- Providers: 75%+
- Utilities: 70%+
- Configuration: 70%+

## Running Tests

```bash
# Run all tests with coverage
python3 -m pytest tests/ --cov=app --cov-report=html --cov-report=term

# Run specific test file
python3 -m pytest tests/api/test_runs.py -v

# Run with coverage for specific module
python3 -m pytest tests/api/ --cov=app/api --cov-report=term-missing
```

## Next Steps

1. ✅ Create tests for API endpoints (runs, threads)
2. Create tests for core configuration
3. Create tests for providers (GigaChat, ChromaDB, Milvus)
4. Create tests for RAG chain
5. Create tests for reasoning engines
6. Create tests for factories
7. Create tests for repositories
8. Run coverage analysis and identify gaps
9. Add missing tests for uncovered code paths
10. Document test patterns and best practices

## Notes

- Focus on testing business logic, not framework code
- Prioritize tests that catch real bugs
- Keep tests maintainable and readable
- Use descriptive test names
- Group related tests in classes
- Use parametrize for similar test cases with different inputs
