# Руководство по замене LLM модели

## Обзор

Данное руководство описывает процесс добавления новой LLM модели или замены существующей в Python AI Service. Архитектура сервиса построена на интерфейсах, что позволяет легко добавлять новые провайдеры моделей без изменения бизнес-логики.

## Архитектура моделей

### Компоненты

```
ModelFactory (Фабрика)
    ↓
IModelProvider (Интерфейс)
    ↓
Конкретные провайдеры:
    • GigaChatProvider
    • VLLMProvider
    • YourNewProvider ← добавляем здесь
```

### Интерфейс IModelProvider

Все провайдеры моделей должны реализовывать интерфейс `IModelProvider`:

```python
# app/interfaces/model_provider.py

class IModelProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> ModelResponse:
        """Генерация ответа на промпт."""
        pass
    
    @abstractmethod
    async def stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> AsyncGenerator[StreamChunk, None]:
        """Стриминг ответа."""
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """Проверка доступности модели."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Закрытие соединений и освобождение ресурсов."""
        pass
```

## Шаги по добавлению новой модели

### Шаг 1: Создание провайдера

Создайте новый файл в `app/providers/models/`:

```python
# app/providers/models/your_model_provider.py

import logging
from typing import AsyncGenerator, Dict, Any, Optional
from app.interfaces.model_provider import (
    IModelProvider,
    ModelResponse,
    StreamChunk,
    ModelError,
    ModelUnavailableError
)

logger = logging.getLogger(__name__)


class YourModelProvider(IModelProvider):
    """
    Провайдер для вашей LLM модели.
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.yourmodel.com",
        model_name: str = "your-model-v1",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ):
        """
        Инициализация провайдера.
        
        Args:
            api_key: API ключ для аутентификации
            base_url: URL API
            model_name: Название модели
            temperature: Температура генерации
            max_tokens: Максимальное количество токенов
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Инициализация клиента (например, aiohttp)
        self._client = None
        self._session = None
    
    async def _ensure_client(self):
        """Ленивая инициализация HTTP клиента."""
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
    
    async def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ModelResponse:
        """
        Генерация ответа.
        
        Args:
            prompt: Текст промпта
            temperature: Температура (опционально)
            max_tokens: Макс. токенов (опционально)
            
        Returns:
            ModelResponse с результатом
            
        Raises:
            ModelError: При ошибке генерации
            ModelUnavailableError: Если модель недоступна
        """
        await self._ensure_client()
        
        try:
            # Подготовка запроса
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "temperature": temperature or self.temperature,
                "max_tokens": max_tokens or self.max_tokens,
                **kwargs
            }
            
            # Отправка запроса
            async with self._session.post(
                f"{self.base_url}/v1/completions",
                json=payload
            ) as response:
                if response.status == 503:
                    raise ModelUnavailableError(
                        self.model_name,
                        "Model service unavailable"
                    )
                
                if response.status != 200:
                    error_text = await response.text()
                    raise ModelError(
                        self.model_name,
                        f"API error: {error_text}"
                    )
                
                data = await response.json()
                
                # Парсинг ответа
                return ModelResponse(
                    content=data["choices"][0]["text"],
                    model=self.model_name,
                    usage={
                        "prompt_tokens": data["usage"]["prompt_tokens"],
                        "completion_tokens": data["usage"]["completion_tokens"],
                        "total_tokens": data["usage"]["total_tokens"]
                    },
                    metadata={
                        "finish_reason": data["choices"][0]["finish_reason"]
                    }
                )
        
        except ModelError:
            raise
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise ModelError(self.model_name, str(e))
    
    async def stream(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Стриминг ответа.
        
        Args:
            prompt: Текст промпта
            temperature: Температура
            max_tokens: Макс. токенов
            
        Yields:
            StreamChunk с частями ответа
        """
        await self._ensure_client()
        
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "temperature": temperature or self.temperature,
                "max_tokens": max_tokens or self.max_tokens,
                "stream": True,
                **kwargs
            }
            
            async with self._session.post(
                f"{self.base_url}/v1/completions",
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ModelError(
                        self.model_name,
                        f"Stream error: {error_text}"
                    )
                
                # Чтение SSE потока
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    
                    if not line or line == "data: [DONE]":
                        continue
                    
                    if line.startswith("data: "):
                        import json
                        data = json.loads(line[6:])
                        
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            
                            if content:
                                yield StreamChunk(
                                    content=content,
                                    model=self.model_name,
                                    finish_reason=delta.get("finish_reason")
                                )
        
        except Exception as e:
            logger.error(f"Error streaming response: {e}")
            raise ModelError(self.model_name, str(e))
    
    async def is_available(self) -> bool:
        """
        Проверка доступности модели.
        
        Returns:
            True если модель доступна
        """
        try:
            await self._ensure_client()
            
            async with self._session.get(
                f"{self.base_url}/health",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                return response.status == 200
        
        except Exception as e:
            logger.warning(f"Model availability check failed: {e}")
            return False
    
    async def close(self) -> None:
        """Закрытие HTTP сессии."""
        if self._session:
            await self._session.close()
            self._session = None
            logger.info(f"Closed {self.model_name} provider")
```

### Шаг 2: Добавление конфигурации

Добавьте настройки в `app/core/config.py`:

```python
# app/core/config.py

class Settings(BaseSettings):
    # ... существующие настройки ...
    
    # Your Model Configuration
    YOUR_MODEL_API_KEY: str = ""
    YOUR_MODEL_BASE_URL: str = "https://api.yourmodel.com"
    YOUR_MODEL_NAME: str = "your-model-v1"
    YOUR_MODEL_TEMPERATURE: float = 0.7
    YOUR_MODEL_MAX_TOKENS: int = 1000
    
    YOUR_MODEL_CONFIG: Dict[str, Any] = {
        "api_key": os.getenv("YOUR_MODEL_API_KEY", ""),
        "base_url": os.getenv("YOUR_MODEL_BASE_URL", "https://api.yourmodel.com"),
        "model_name": os.getenv("YOUR_MODEL_NAME", "your-model-v1"),
        "temperature": float(os.getenv("YOUR_MODEL_TEMPERATURE", "0.7")),
        "max_tokens": int(os.getenv("YOUR_MODEL_MAX_TOKENS", "1000")),
    }
    
    def get_model_config(self, model_name: str) -> Dict[str, Any]:
        """Получить конфигурацию модели."""
        configs = {
            "vllm": self.VLLM_CONFIG,
            "gigachat": self.GIGACHAT_BASE_CONFIG,
            "gigachat_pro": self.GIGACHAT_PRO_CONFIG,
            "gigachat_max": self.GIGACHAT_MAX_CONFIG,
            "your_model": self.YOUR_MODEL_CONFIG,  # ← добавить
        }
        return configs.get(model_name.lower(), self.GIGACHAT_BASE_CONFIG)
    
    def get_available_models(self) -> List[str]:
        """Список доступных моделей."""
        return [
            "vllm",
            "gigachat",
            "gigachat_pro",
            "gigachat_max",
            "your_model"  # ← добавить
        ]
```

### Шаг 3: Регистрация в фабрике

Обновите `app/factory/model_factory.py`:

```python
# app/factory/model_factory.py

from app.providers.models.your_model_provider import YourModelProvider

class ModelFactory:
    # ... существующий код ...
    
    _fallback_order: List[str] = [
        "gigachat",
        "gigachat_pro",
        "gigachat_max",
        "vllm",
        "your_model"  # ← добавить в fallback
    ]
    
    @classmethod
    def _create_provider(cls, model_name: str) -> IModelProvider:
        """Создание провайдера."""
        logger.info(f"Creating provider for model: {model_name}")
        
        # ... существующие провайдеры ...
        
        elif model_name == "your_model":
            return YourModelProvider(
                api_key=settings.YOUR_MODEL_API_KEY,
                base_url=settings.YOUR_MODEL_BASE_URL,
                model_name=settings.YOUR_MODEL_NAME,
                temperature=settings.YOUR_MODEL_TEMPERATURE,
                max_tokens=settings.YOUR_MODEL_MAX_TOKENS
            )
        
        else:
            raise ValueError(f"Unknown model: {model_name}")
    
    @classmethod
    def get_available_models(cls) -> List[str]:
        """Список доступных моделей."""
        return [
            "vllm",
            "gigachat",
            "gigachat_pro",
            "gigachat_max",
            "your_model"  # ← добавить
        ]
```

### Шаг 4: Добавление переменных окружения

Обновите `.env` файл:

```bash
# Your Model Configuration
YOUR_MODEL_API_KEY=your-api-key-here
YOUR_MODEL_BASE_URL=https://api.yourmodel.com
YOUR_MODEL_NAME=your-model-v1
YOUR_MODEL_TEMPERATURE=0.7
YOUR_MODEL_MAX_TOKENS=1000

# Установить как текущую модель (опционально)
# CURRENT_MODEL=your_model
```

### Шаг 5: Тестирование

Создайте тестовый скрипт:

```python
# scripts/test_your_model.py

import asyncio
import os
import sys

# Добавить корень проекта в путь
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.factory.model_factory import ModelFactory


async def test_your_model():
    """Тест новой модели."""
    print("=" * 60)
    print("Testing Your Model Provider")
    print("=" * 60)
    
    try:
        # 1. Получить провайдер
        print("\n1. Getting model provider...")
        provider = ModelFactory.get_model("your_model")
        print(f"✓ Provider created: {provider.__class__.__name__}")
        
        # 2. Проверить доступность
        print("\n2. Checking availability...")
        is_available = await provider.is_available()
        print(f"✓ Model available: {is_available}")
        
        if not is_available:
            print("✗ Model is not available. Check your configuration.")
            return
        
        # 3. Тест генерации
        print("\n3. Testing generation...")
        test_prompt = "Привет! Как дела?"
        
        response = await provider.generate(
            prompt=test_prompt,
            temperature=0.7,
            max_tokens=100
        )
        
        print(f"✓ Response received:")
        print(f"  Content: {response.content[:100]}...")
        print(f"  Model: {response.model}")
        print(f"  Tokens: {response.usage}")
        
        # 4. Тест стриминга
        print("\n4. Testing streaming...")
        print("Stream output: ", end="", flush=True)
        
        async for chunk in provider.stream(
            prompt=test_prompt,
            temperature=0.7,
            max_tokens=100
        ):
            print(chunk.content, end="", flush=True)
        
        print("\n✓ Streaming completed")
        
        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
    
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Очистка ресурсов
        print("\n5. Cleaning up...")
        await ModelFactory.close_all()
        print("✓ Resources cleaned up")


if __name__ == "__main__":
    asyncio.run(test_your_model())
```

Запустите тест:

```bash
python3 scripts/test_your_model.py
```

## Примеры интеграции

### Пример 1: OpenAI-совместимый API

```python
class OpenAICompatibleProvider(IModelProvider):
    """Провайдер для OpenAI-совместимых API."""
    
    def __init__(self, api_key: str, base_url: str, model: str):
        from openai import AsyncOpenAI
        
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = model
    
    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        response = await self.client.completions.create(
            model=self.model,
            prompt=prompt,
            **kwargs
        )
        
        return ModelResponse(
            content=response.choices[0].text,
            model=self.model,
            usage=response.usage.dict()
        )
```

### Пример 2: Anthropic Claude

```python
class ClaudeProvider(IModelProvider):
    """Провайдер для Anthropic Claude."""
    
    def __init__(self, api_key: str, model: str = "claude-3-opus-20240229"):
        from anthropic import AsyncAnthropic
        
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
    
    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        message = await self.client.messages.create(
            model=self.model,
            max_tokens=kwargs.get("max_tokens", 1024),
            messages=[{"role": "user", "content": prompt}]
        )
        
        return ModelResponse(
            content=message.content[0].text,
            model=self.model,
            usage={
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens
            }
        )
```

### Пример 3: Локальная модель через Transformers

```python
class HuggingFaceProvider(IModelProvider):
    """Провайдер для локальных моделей через Transformers."""
    
    def __init__(self, model_name: str, device: str = "cuda"):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map=device
        )
        self.model_name = model_name
    
    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=kwargs.get("max_tokens", 100),
            temperature=kwargs.get("temperature", 0.7),
            do_sample=True
        )
        
        text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        return ModelResponse(
            content=text,
            model=self.model_name,
            usage={"total_tokens": len(outputs[0])}
        )
```

## Лучшие практики

### 1. Обработка ошибок

```python
async def generate(self, prompt: str, **kwargs) -> ModelResponse:
    try:
        # Попытка генерации
        response = await self._make_request(prompt, **kwargs)
        return response
    
    except ConnectionError as e:
        # Проблемы с сетью
        raise ModelUnavailableError(self.model_name, f"Connection failed: {e}")
    
    except TimeoutError as e:
        # Таймаут
        raise ModelError(self.model_name, f"Request timeout: {e}")
    
    except Exception as e:
        # Другие ошибки
        logger.error(f"Unexpected error: {e}")
        raise ModelError(self.model_name, str(e))
```

### 2. Retry логика

```python
from tenacity import retry, stop_after_attempt, wait_exponential

class RobustProvider(IModelProvider):
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        # Автоматические повторы при ошибках
        return await self._generate_impl(prompt, **kwargs)
```

### 3. Rate Limiting

```python
from aiolimiter import AsyncLimiter

class RateLimitedProvider(IModelProvider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 10 запросов в минуту
        self.limiter = AsyncLimiter(10, 60)
    
    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        async with self.limiter:
            return await self._generate_impl(prompt, **kwargs)
```

### 4. Кэширование

```python
from functools import lru_cache
import hashlib

class CachedProvider(IModelProvider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache = {}
    
    def _cache_key(self, prompt: str, **kwargs) -> str:
        """Генерация ключа кэша."""
        key_str = f"{prompt}:{kwargs}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        cache_key = self._cache_key(prompt, **kwargs)
        
        if cache_key in self._cache:
            logger.info("Cache hit")
            return self._cache[cache_key]
        
        response = await self._generate_impl(prompt, **kwargs)
        self._cache[cache_key] = response
        
        return response
```

## Troubleshooting

### Проблема: Модель не регистрируется

**Решение**:
1. Проверьте импорт в `model_factory.py`
2. Убедитесь что имя модели добавлено в `get_available_models()`
3. Проверьте что `_create_provider()` обрабатывает новое имя

### Проблема: Ошибки аутентификации

**Решение**:
1. Проверьте API ключ в `.env`
2. Убедитесь что ключ не содержит пробелов
3. Проверьте формат заголовков аутентификации

### Проблема: Таймауты

**Решение**:
1. Увеличьте таймаут в конфигурации
2. Добавьте retry логику
3. Проверьте сетевое соединение

## Ссылки

- [Architecture](../architecture.md)
- [Configuration](../configuration.md)
- [Model Factory Code](../../app/factory/model_factory.py)
- [IModelProvider Interface](../../app/interfaces/model_provider.py)
