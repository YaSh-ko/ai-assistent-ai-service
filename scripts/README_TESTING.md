# Testing Scripts Guide

## Quick Start

### Run Tests the Easy Way

Use the test runner script:

```bash
# Show usage
bash scripts/run_tests.sh

# Run all tests
bash scripts/run_tests.sh all

# Run specific test file
bash scripts/run_tests.sh tests/e2e/test_rag_reasoning.py

# Run test category
bash scripts/run_tests.sh reasoning
bash scripts/run_tests.sh services
bash scripts/run_tests.sh e2e
```

## Common Test Commands

### Using pytest directly

```bash
# Run all tests
python3 -m pytest

# Run with verbose output
python3 -m pytest -v

# Run specific file
python3 -m pytest tests/services/test_reasoning_service.py -v

# Run specific test function
python3 -m pytest tests/e2e/test_rag_reasoning.py::test_rag_reasoning -v

# Run tests matching pattern
python3 -m pytest -k "reasoning" -v

# Stop on first failure
python3 -m pytest -x

# Show print statements
python3 -m pytest -s
```

### Test Categories

```bash
# Unit tests (fast)
python3 -m pytest tests/ --ignore=tests/e2e --ignore=tests/integration -v

# E2E tests (slower, requires services)
python3 -m pytest tests/e2e/ -v

# Service tests
python3 -m pytest tests/services/ -v

# Provider tests
python3 -m pytest tests/providers/ -v

# Reasoning tests
python3 -m pytest tests/services/test_reasoning_service.py tests/providers/test_reasoning.py -v
```

## ❌ Common Mistakes

### DON'T Run Tests Directly

```bash
# ❌ WRONG - Will fail with ModuleNotFoundError
python3 tests/test_file.py
python3 tests/e2e/test_rag_reasoning.py
/bin/python3 /path/to/test_file.py
```

### ✅ DO Use pytest

```bash
# ✓ CORRECT
python3 -m pytest tests/test_file.py
pytest tests/test_file.py -v
bash scripts/run_tests.sh tests/test_file.py
```

## Why Use pytest?

Pytest properly:
- Sets up Python path (includes project root)
- Configures test environment
- Handles fixtures and dependencies
- Provides better error messages
- Supports async tests
- Manages test isolation

## Test Structure

```
tests/
├── api/                    # API endpoint tests
├── chains/                 # Chain tests (RAG, CAG)
├── core/                   # Core functionality tests
├── data_access/            # Database access tests
├── e2e/                    # End-to-end tests
│   ├── conftest.py         # E2E fixtures
│   ├── utils.py            # E2E utilities
│   └── test_*.py           # E2E test files
├── integration/            # Integration tests
├── models/                 # Model provider tests
├── providers/              # Provider tests
│   └── test_reasoning.py   # Reasoning factory tests
├── search/                 # Search engine tests
├── services/               # Service layer tests
│   └── test_reasoning_service.py  # Reasoning service tests
└── conftest.py             # Shared fixtures
```

## Debugging Tests

### Verbose Output

```bash
python3 -m pytest -v -s tests/test_file.py
```

### Stop on First Failure

```bash
python3 -m pytest -x tests/
```

### Run Last Failed Tests

```bash
python3 -m pytest --lf
```

### Show Local Variables on Failure

```bash
python3 -m pytest -l tests/test_file.py
```

### Debug with PDB

```bash
python3 -m pytest --pdb tests/test_file.py
```

### Show Test Duration

```bash
python3 -m pytest --durations=10 tests/
```

## Test Coverage

```bash
# Run with coverage
python3 -m pytest --cov=app --cov-report=html

# View coverage report
open htmlcov/index.html
```

## Continuous Integration

Tests run automatically on:
- Pull requests
- Commits to main branch
- Scheduled nightly builds

## Prerequisites

### Install Test Dependencies

```bash
pip install pytest pytest-asyncio pytest-cov
```

### Required Services for E2E Tests

- PostgreSQL (port 5432)
- Neo4j (port 7687)
- ChromaDB (port 8001) or Milvus (port 19530)
- Redis (optional)

### Check Services

```bash
# PostgreSQL
psql -h localhost -p 5432 -U your_user -d your_db

# Neo4j
curl http://localhost:7474

# ChromaDB
curl http://localhost:8001/api/v1/heartbeat

# Milvus
python3 scripts/test_milvus_vector_store.py
```

## Test Configuration

### pytest.ini

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
```

### Environment Variables

Tests use `.env` file for configuration. You can override for tests:

```bash
# Use test database
DATABASE_URL=postgresql://user:pass@localhost:5432/test_db python3 -m pytest

# Use different vector store
VECTOR_STORE_TYPE=milvus python3 -m pytest tests/e2e/
```

## Writing New Tests

### Test File Template

```python
import pytest

@pytest.mark.asyncio
async def test_my_feature():
    """Test description."""
    # Arrange
    input_data = "test"
    
    # Act
    result = await my_function(input_data)
    
    # Assert
    assert result == expected
```

### Using Fixtures

```python
@pytest.fixture
def mock_service():
    """Create mock service."""
    service = MockService()
    yield service
    service.cleanup()

def test_with_fixture(mock_service):
    """Test using fixture."""
    result = mock_service.do_something()
    assert result is not None
```

## Troubleshooting

### Tests Not Found

```bash
# Check pytest can discover tests
python3 -m pytest --collect-only
```

### Import Errors

```bash
# Ensure you're in project root
pwd  # Should show .../python-ai-service

# Run from project root
python3 -m pytest tests/
```

### Async Test Warnings

Add to `pytest.ini`:
```ini
asyncio_default_fixture_loop_scope = function
```

### Database Connection Errors

```bash
# Check services are running
docker ps

# Check connection settings in .env
cat .env | grep -E "(POSTGRES|NEO4J|CHROMA|MILVUS)"
```

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [Testing Guide](../docs/TESTING_GUIDE.md)
- [Troubleshooting](../docs/TROUBLESHOOTING.md)
