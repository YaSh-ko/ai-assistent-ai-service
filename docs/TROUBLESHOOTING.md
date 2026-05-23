# Troubleshooting Guide

## Common Issues and Solutions

### 1. Unclosed Client Session Errors

**Error:**
```
ERROR | asyncio | Unclosed client session
client_session: <aiohttp.client.ClientSession object at 0x...>
ERROR | asyncio | Unclosed connector
```

**Cause:** HTTP sessions from model providers (like GigaChat) are not being properly closed.

**Solution:** Always call `ModelFactory.close_all()` to clean up resources:

```python
from app.factory.model_factory import ModelFactory

async def my_function():
    try:
        # Your code here
        provider = ModelFactory.get_model("gigachat_pro")
        result = await provider.generate("test")
    finally:
        # Always clean up
        await ModelFactory.close_all()
```

**In Scripts:**
```python
async def main():
    try:
        # Your logic
        pass
    finally:
        from app.factory.model_factory import ModelFactory
        await ModelFactory.close_all()
        print("✓ Resources cleaned up")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 2. GigaChat Authentication Errors

**Error:**
```
Can't decode 'Authorization' header
```

**Cause:** Using `GIGACHAT_CREDENTIALS` (pre-encoded base64) instead of `CLIENT_ID` + `CLIENT_SECRET`.

**Solution:**

1. Comment out `GIGACHAT_CREDENTIALS` in `.env`:
```bash
#GIGACHAT_CREDENTIALS=MDE5YTkyNzctMjc3Yy03MzJhLThlYzgtNTZjMDMxMzM4OTAyOjViM2I1OTNiLTkwZTMtNGE5Yy1iYTJiLWM1YjhiYTRiM2E1Yg==
GIGACHAT_CLIENT_ID=your-client-id
GIGACHAT_CLIENT_SECRET=your-client-secret
```

2. In scripts, explicitly clear the env variable:
```python
import os
os.environ.pop('GIGACHAT_CREDENTIALS', None)
```

See [GIGACHAT_AUTH_TROUBLESHOOTING.md](./GIGACHAT_AUTH_TROUBLESHOOTING.md) for details.

---

### 3. ModuleNotFoundError: No module named 'app' or 'tests'

**Error:**
```
ModuleNotFoundError: No module named 'app'
ModuleNotFoundError: No module named 'tests'
```

**Cause:** Running test files directly instead of using pytest.

**Solution:**

❌ **Wrong:**
```bash
python3 tests/test_file.py
python3 tests/e2e/test_rag_reasoning.py
/bin/python3 /path/to/test_file.py
```

✅ **Correct:**
```bash
# From project root
python3 -m pytest tests/test_file.py

# Or simply
pytest tests/test_file.py -v

# For e2e tests
python3 -m pytest tests/e2e/test_rag_reasoning.py -v

# Run all tests
python3 -m pytest

# Run specific test function
python3 -m pytest tests/e2e/test_rag_reasoning.py::test_rag_reasoning -v
```

**Why?** Pytest properly sets up the Python path and test environment. Running tests directly doesn't include the project root in `sys.path`.

---

### 4. Rate Limit Errors (HTTP 429)

**Error:**
```
HTTP 429 "Too Many Requests"
```

**Cause:** Exceeding GigaChat API rate limits (~10 requests/minute).

**Solution:**

1. Use conservative test parameters:
```bash
# Instead of 50 users at 50 RPS
python3 scripts/stress_test.py --users 5 --rate 3
```

2. Use the conservative stress test script:
```bash
bash scripts/conservative_stress_test.sh
```

3. Add delays between requests:
```python
import asyncio
await asyncio.sleep(6)  # Wait 6 seconds between requests
```

See [STRESS_TESTING_RATE_LIMITS.md](./stress_testing/STRESS_TESTING_RATE_LIMITS.md) for details.

---

### 5. Port Already in Use

**Error:**
```
Address already in use: 0.0.0.0:8000
```

**Cause:** ChromaDB or another service is using port 8000.

**Solution:**

1. Use port 8001 for the service:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

2. Update test scripts to use port 8001:
```python
BASE_URL = "http://localhost:8001"
```

See [STRESS_TESTING_PORT_GUIDE.md](./stress_testing/STRESS_TESTING_PORT_GUIDE.md) for details.

---

### 6. Async Test Warnings

**Warning:**
```
PytestDeprecationWarning: asyncio_default_fixture_loop_scope is unset
```

**Solution:** Add to `pytest.ini`:
```ini
[pytest]
asyncio_default_fixture_loop_scope = function
```

---

### 7. Database Connection Errors

**Error:**
```
Connection refused: localhost:5432
```

**Cause:** PostgreSQL is not running or wrong port.

**Solution:**

1. Check if PostgreSQL is running:
```bash
sudo systemctl status postgresql
```

2. Verify connection settings in `.env`:
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=your_database
```

3. Test connection:
```bash
psql -h localhost -p 5432 -U your_user -d your_database
```

---

### 8. Import Errors in Tests

**Error:**
```
ImportError: cannot import name 'logger' from 'app.core.logging'
```

**Cause:** Using wrong import path for logging.

**Solution:** Use standard Python logging:

❌ **Wrong:**
```python
from app.core.logging import logger
```

✅ **Correct:**
```python
import logging
logger = logging.getLogger(__name__)
```

---

### 9. Reflection Engine Quality Threshold Not Met

**Issue:** Reflection engine reaches max iterations without meeting quality threshold.

**Solution:**

1. Lower the quality threshold:
```bash
REFLECTION_QUALITY_THRESHOLD=0.7  # Instead of 0.8
```

2. Increase max iterations:
```bash
REFLECTION_MAX_ITERATIONS=5  # Instead of 3
```

3. Adjust temperatures:
```bash
REFLECTION_CRITIQUE_TEMP=0.2      # More focused critique
REFLECTION_REFINEMENT_TEMP=0.8    # More creative refinement
```

---

### 10. Memory Leaks in Long-Running Services

**Issue:** Memory usage grows over time.

**Solution:**

1. Clear reasoning factory cache periodically:
```python
from app.factory.reasoning_factory import ReasoningFactory
ReasoningFactory._instances.clear()
```

2. Close model providers after use:
```python
await ModelFactory.close_all()
```

3. Monitor memory usage:
```bash
python3 scripts/monitor_performance.py
```

---

## Getting Help

If you encounter an issue not covered here:

1. Check the logs:
```bash
tail -f logs/app.log
```

2. Enable debug logging:
```bash
LOG_LEVEL=DEBUG python3 your_script.py
```

3. Run with verbose output:
```bash
python3 -m pytest -v -s tests/your_test.py
```

4. Check the documentation:
- [Testing Guide](./TESTING_GUIDE.md)
- [Stress Testing Guide](./stress_testing/STRESS_TESTING_GUIDE.md)
- [Model Testing Guide](./MODEL_TESTING_GUIDE.md)

---

## Best Practices

### Always Clean Up Resources

```python
async def main():
    try:
        # Your code
        pass
    finally:
        await ModelFactory.close_all()
```

### Use Context Managers When Possible

```python
async with aiohttp.ClientSession() as session:
    # Use session
    pass
# Automatically closed
```

### Handle Errors Gracefully

```python
try:
    result = await provider.generate(prompt)
except ModelUnavailableError:
    # Fallback to another model
    pass
except RateLimitError as e:
    # Wait and retry
    await asyncio.sleep(e.retry_after or 60)
```

### Test with Conservative Parameters

Start with low load and gradually increase:
```bash
# Start small
python3 scripts/stress_test.py --users 1 --rate 1

# Gradually increase
python3 scripts/stress_test.py --users 5 --rate 3
```
