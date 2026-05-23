# Testing Guide

## Running Tests

### All Tests
```bash
python3 -m pytest
```

### Specific Test Files
```bash
# Reasoning service tests
python3 -m pytest tests/services/test_reasoning_service.py -v

# Reasoning provider tests
python3 -m pytest tests/providers/test_reasoning.py -v

# E2E tests
python3 -m pytest tests/e2e/ -v
```

### Test Coverage
```bash
python3 -m pytest --cov=app --cov-report=html
```

## Test Structure

```
tests/
├── api/                    # API endpoint tests
├── chains/                 # Chain tests (RAG, CAG)
├── core/                   # Core functionality tests
├── data_access/            # Database access tests
├── e2e/                    # End-to-end tests
├── integration/            # Integration tests
├── models/                 # Model provider tests
├── providers/              # Provider tests
│   └── test_reasoning.py   # Reasoning factory & provider tests
├── search/                 # Search engine tests
├── services/               # Service layer tests
│   └── test_reasoning_service.py  # Reasoning service tests
└── conftest.py             # Shared fixtures
```

## Reasoning Tests

### ReasoningService Tests (`tests/services/test_reasoning_service.py`)

Tests for the reasoning service orchestration layer:

- `test_reasoning_service_execution` - Basic execution flow
- `test_reasoning_service_with_context` - Context passing
- `test_reasoning_service_error_handling` - Error handling
- `test_reasoning_service_engine_selection` - Engine selection logic
- `test_reasoning_service_get_reasoning_info` - History retrieval
- `test_reasoning_service_warmup` - Engine initialization
- `test_reasoning_service_fallback_to_default` - Fallback behavior

### Reasoning Provider Tests (`tests/providers/test_reasoning.py`)

Tests for reasoning engine providers and factory:

- `test_reasoning_factory_cot` - CoT engine creation
- `test_reasoning_factory_reflection` - Reflection engine creation
- `test_reasoning_factory_invalid_engine` - Error handling
- `test_reasoning_factory_singleton` - Singleton pattern
- `test_cot_provider_interface` - CoT interface compliance
- `test_reflection_provider_interface` - Reflection interface compliance
- `test_reasoning_factory_clear_cache` - Cache management

## Common Issues

### ModuleNotFoundError: No module named 'app' or 'tests'

**Problem**: Running test files directly with `python3 tests/test_file.py` or `/bin/python3 /path/to/test_file.py`

**Solution**: Always use pytest from the project root:
```bash
# Correct way
python3 -m pytest tests/test_file.py

# Also correct
pytest tests/test_file.py -v

# Run all tests
python3 -m pytest

# Run specific test function
python3 -m pytest tests/e2e/test_rag_reasoning.py::test_rag_reasoning -v
```

**Why?** Pytest properly configures the Python path and test environment. Running tests directly doesn't include the project root in `sys.path`, causing import errors.

### Import Errors

**Problem**: Tests can't find modules

**Solution**: Ensure you're running from the project root directory:
```bash
cd /path/to/python-ai-service
python3 -m pytest
```

### Async Test Warnings

**Problem**: `PytestDeprecationWarning` about `asyncio_default_fixture_loop_scope`

**Solution**: Add to `pytest.ini`:
```ini
[pytest]
asyncio_default_fixture_loop_scope = function
```

## Writing New Tests

### Test File Location

Place tests in the appropriate directory matching the source structure:

- `app/services/my_service.py` → `tests/services/test_my_service.py`
- `app/providers/my_provider.py` → `tests/providers/test_my_provider.py`

### Test Naming

- Test files: `test_*.py`
- Test functions: `test_*`
- Test classes: `Test*`

### Async Tests

Use `@pytest.mark.asyncio` decorator:

```python
@pytest.mark.asyncio
async def test_async_function():
    result = await my_async_function()
    assert result == expected
```

### Mocking

Use `unittest.mock` for mocking:

```python
from unittest.mock import MagicMock, AsyncMock, patch

@pytest.fixture
def mock_service():
    service = AsyncMock()
    service.method.return_value = "result"
    return service

def test_with_mock(mock_service):
    with patch("app.module.Service", return_value=mock_service):
        # Test code
        pass
```

## Test Coverage Goals

- Unit tests: 80%+ coverage
- Integration tests: Key workflows covered
- E2E tests: Critical user paths covered

## CI/CD Integration

Tests run automatically on:
- Pull requests
- Commits to main branch
- Scheduled nightly builds

## Manual Testing

For manual testing of reasoning engines:

```bash
# Test CoT engine
python3 scripts/test_current_model.py

# Test Reflection engine
python3 scripts/test_reflection_engine.py
```

## Debugging Tests

### Verbose Output
```bash
python3 -m pytest -v -s
```

### Stop on First Failure
```bash
python3 -m pytest -x
```

### Run Specific Test
```bash
python3 -m pytest tests/services/test_reasoning_service.py::test_reasoning_service_execution
```

### Show Print Statements
```bash
python3 -m pytest -s
```

### Debug with PDB
```bash
python3 -m pytest --pdb
```
