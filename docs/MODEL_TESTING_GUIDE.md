# Model Testing Guide

## Quick Test: Current Model

Test the model configured in `app/core/config.py` (CURRENT_MODEL):

```bash
# Test with default prompt
python3 scripts/test_current_model.py

# Test with custom prompt
python3 scripts/test_current_model.py --prompt "Расскажи анекдот"
```

## Test All GigaChat Versions

Test all three GigaChat versions (base, pro, max):

```bash
python3 scripts/test_gigachat.py
```

This will test:
- `gigachat` (base)
- `gigachat_pro`
- `gigachat_max`

## Test Specific Model

To test a specific model version, you can modify and use the test function:

```python
from app.factory.model_factory import ModelFactory

async def test_model():
    provider = ModelFactory.get_model("gigachat_pro")
    response = await provider.generate(prompt="Привет!")
    print(response.content)
```

## Available Models

From `app/core/config.py`:

- `gigachat` - Base model (default)
- `gigachat_pro` - Pro version
- `gigachat_max` - Max version

## Configuration

Current model is set in `app/core/config.py`:

```python
CURRENT_MODEL: str = "gigachat"
```

To change the default model, edit this value.

## Troubleshooting

### Authentication Errors

If you see authentication errors:

1. Check `.env` file has valid credentials:
   ```
   GIGACHAT_CLIENT_ID=your_client_id
   GIGACHAT_CLIENT_SECRET=your_client_secret
   ```

2. Verify credentials are correct:
   ```bash
   python3 scripts/test_current_model.py
   ```

3. Check rate limits (see `docs/STRESS_TESTING_RATE_LIMITS.md`)

### Model Not Available

If model reports as "not available":

- Check credentials
- Verify network connectivity
- Check GigaChat API status
- Wait a few minutes if rate limited

## Examples

### Test with Different Prompts

```bash
# Simple greeting
python3 scripts/test_current_model.py --prompt "Привет!"

# Question
python3 scripts/test_current_model.py --prompt "Что такое Python?"

# Complex query
python3 scripts/test_current_model.py --prompt "Объясни квантовую физику простыми словами"
```

### Test in Python Script

```python
import asyncio
from app.factory.model_factory import ModelFactory
from app.core.config import Settings

async def test():
    settings = Settings()
    model = settings.CURRENT_MODEL
    
    provider = ModelFactory.get_model(model)
    
    if await provider.is_available():
        response = await provider.generate(prompt="Тест")
        print(response.content)
    
    await ModelFactory.close_all()

asyncio.run(test())
```

## Integration with Service

The current model is used by:

- `app/services/llm_service.py` - LLM service
- `app/chains/rag_chain.py` - RAG chain
- `app/reasoning/cot_reasoning.py` - CoT reasoning

To test the full service with the current model:

```bash
# Start service
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001

# Test with quick_test.py
python3 scripts/quick_test.py
```
