"""
Тесты для LLM провайдеров и системы моделей.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import AsyncGenerator

from app.interfaces.model_provider import (
    IModelProvider,
    ModelConfig,
    ModelResponse,
    StreamChunk,
    BaseModelProvider,
    ModelError,
    ModelUnavailableError
)
from app.factory.model_factory import ModelFactory
from app.services.llm_service import LLMService
from app.providers.models.gigachat_provider import GigaChatProvider
from app.providers.models.vllm_provider import VLLMProvider


# ============================================
# Test Fixtures
# ============================================

@pytest.fixture
def mock_model_response():
    """Создание mock ModelResponse."""
    return ModelResponse(
        content="Это тестовый ответ от модели.",
        model_name="test_model",
        tokens_used=50,
        prompt_tokens=10,
        completion_tokens=40,
        latency_ms=123.45,
        finish_reason="stop"
    )


@pytest.fixture
def mock_stream_chunks():
    """Создание mock stream chunks."""
    return [
        StreamChunk(content="Привет", is_final=False, model_name="test_model"),
        StreamChunk(content=", ", is_final=False, model_name="test_model"),
        StreamChunk(content="мир!", is_final=False, model_name="test_model"),
        StreamChunk(content="", is_final=True, model_name="test_model", finish_reason="stop"),
    ]


class MockModelProvider(BaseModelProvider):
    """Mock провайдер для тестов."""
    
    def __init__(self, name: str = "mock_model"):
        config = ModelConfig(
            model_name=name,
            temperature=0.7,
            max_tokens=100
        )
        super().__init__(config)
        self._name = name
        self._available = True
    
    @property
    def name(self) -> str:
        return self._name
    
    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        return ModelResponse(
            content=f"Mock response for: {prompt[:50]}",
            model_name=self._name,
            tokens_used=len(prompt.split()),
            latency_ms=10.0
        )
    
    async def stream(self, prompt: str, **kwargs) -> AsyncGenerator[StreamChunk, None]:
        words = prompt.split()[:3]
        for word in words:
            yield StreamChunk(content=word + " ", is_final=False, model_name=self._name)
        yield StreamChunk(content="", is_final=True, model_name=self._name, finish_reason="stop")
    
    async def is_available(self) -> bool:
        return self._available
    
    def set_available(self, available: bool):
        self._available = available


# ============================================
# ModelResponse Tests
# ============================================

class TestModelResponse:
    """Тесты для ModelResponse."""
    
    def test_model_response_creation(self):
        """Тест создания ModelResponse."""
        response = ModelResponse(
            content="Test content",
            model_name="test_model",
            tokens_used=10
        )
        
        assert response.content == "Test content"
        assert response.model_name == "test_model"
        assert response.tokens_used == 10
        assert response.finish_reason == "stop"
    
    def test_model_response_from_error(self):
        """Тест создания ModelResponse из ошибки."""
        error = ValueError("Test error")
        response = ModelResponse.from_error(error, "error_model")
        
        assert "Error:" in response.content
        assert response.model_name == "error_model"
        assert response.finish_reason == "error"


class TestModelConfig:
    """Тесты для ModelConfig."""
    
    def test_model_config_creation(self):
        """Тест создания ModelConfig."""
        config = ModelConfig(
            model_name="test",
            temperature=0.5,
            max_tokens=1000
        )
        
        assert config.model_name == "test"
        assert config.temperature == 0.5
        assert config.max_tokens == 1000
    
    def test_model_config_to_dict(self):
        """Тест конвертации в dict."""
        config = ModelConfig(model_name="test")
        d = config.to_dict()
        
        assert "model_name" in d
        assert "temperature" in d
        assert "max_tokens" in d


# ============================================
# BaseModelProvider Tests
# ============================================

class TestBaseModelProvider:
    """Тесты для BaseModelProvider."""
    
    def test_set_parameters_temperature(self):
        """Тест изменения temperature."""
        provider = MockModelProvider()
        provider.set_parameters(temperature=0.3)
        
        assert provider.get_config().temperature == 0.3
    
    def test_set_parameters_invalid_temperature(self):
        """Тест невалидной temperature."""
        provider = MockModelProvider()
        
        with pytest.raises(ValueError):
            provider.set_parameters(temperature=1.5)
    
    def test_set_parameters_max_tokens(self):
        """Тест изменения max_tokens."""
        provider = MockModelProvider()
        provider.set_parameters(max_tokens=500)
        
        assert provider.get_config().max_tokens == 500
    
    def test_set_parameters_invalid_max_tokens(self):
        """Тест невалидного max_tokens."""
        provider = MockModelProvider()
        
        with pytest.raises(ValueError):
            provider.set_parameters(max_tokens=-10)


# ============================================
# ModelFactory Tests
# ============================================

class TestModelFactory:
    """Тесты для ModelFactory."""
    
    def setup_method(self):
        """Очистка кеша перед каждым тестом."""
        ModelFactory.clear_cache()
    
    def test_get_available_models(self):
        """Тест получения списка доступных моделей."""
        models = ModelFactory.get_available_models()
        
        assert "vllm" in models
        assert "gigachat" in models
        assert "gigachat_pro" in models
        assert "gigachat_max" in models
    
    def test_get_model_gigachat(self):
        """Тест создания GigaChat провайдера."""
        provider = ModelFactory.get_model("gigachat")
        
        assert provider is not None
        assert isinstance(provider, GigaChatProvider)
    
    def test_get_model_vllm(self):
        """Тест создания VLLM провайдера."""
        provider = ModelFactory.get_model("vllm")
        
        assert provider is not None
        assert isinstance(provider, VLLMProvider)
    
    def test_get_model_caching(self):
        """Тест кеширования провайдеров."""
        provider1 = ModelFactory.get_model("gigachat")
        provider2 = ModelFactory.get_model("gigachat")
        
        assert provider1 is provider2
    
    def test_get_model_unknown(self):
        """Тест ошибки для неизвестной модели."""
        with pytest.raises(ValueError):
            ModelFactory.get_model("unknown_model")
    
    def test_set_current_model(self):
        """Тест установки текущей модели."""
        ModelFactory.set_current_model("gigachat_pro")
        
        assert ModelFactory.get_current_model() == "gigachat_pro"
    
    def test_set_current_model_invalid(self):
        """Тест ошибки при установке неизвестной модели."""
        with pytest.raises(ValueError):
            ModelFactory.set_current_model("invalid_model")
    
    def test_clear_cache_specific(self):
        """Тест очистки кеша для конкретной модели."""
        provider1 = ModelFactory.get_model("gigachat")
        ModelFactory.clear_cache("gigachat")
        provider2 = ModelFactory.get_model("gigachat")
        
        assert provider1 is not provider2


# ============================================
# LLMService Tests
# ============================================

class TestLLMService:
    """Тесты для LLMService."""
    
    def setup_method(self):
        """Подготовка к тестам."""
        ModelFactory.clear_cache()
    
    @pytest_asyncio.fixture
    async def llm_service(self):
        """Создание LLMService."""
        return LLMService()
    
    def test_get_available_models(self):
        """Тест получения списка моделей."""
        service = LLMService()
        models = service.get_available_models()
        
        assert len(models) > 0
        assert "gigachat" in models
    
    def test_get_current_model(self):
        """Тест получения текущей модели."""
        service = LLMService()
        current = service.get_current_model()
        
        assert current is not None
        assert isinstance(current, str)
    
    def test_set_current_model(self):
        """Тест изменения текущей модели."""
        service = LLMService()
        service.set_current_model("gigachat_max")
        
        assert service.get_current_model() == "gigachat_max"


# ============================================
# Provider-specific Tests (with mocking)
# ============================================

class TestGigaChatProvider:
    """Тесты для GigaChatProvider."""
    
    def test_provider_creation_base(self):
        """Тест создания base версии."""
        provider = GigaChatProvider(version="base")
        
        assert provider.name == "gigachat"
        assert provider.model_name == "GigaChat"
    
    def test_provider_creation_pro(self):
        """Тест создания pro версии."""
        provider = GigaChatProvider(version="pro")
        
        assert provider.name == "gigachat_pro"
        assert provider.model_name == "GigaChat-Pro"
    
    def test_provider_creation_max(self):
        """Тест создания max версии."""
        provider = GigaChatProvider(version="max")
        
        assert provider.name == "gigachat_max"
        assert provider.model_name == "GigaChat-Max"
    
    def test_provider_creation_invalid_version(self):
        """Тест ошибки при неверной версии."""
        with pytest.raises(ValueError):
            GigaChatProvider(version="invalid")
    
    def test_default_config_base(self):
        """Тест дефолтной конфигурации base."""
        provider = GigaChatProvider(version="base")
        config = provider.get_config()
        
        assert config.temperature == 0.3
        assert config.max_tokens == 1000
    
    def test_default_config_pro(self):
        """Тест дефолтной конфигурации pro."""
        provider = GigaChatProvider(version="pro")
        config = provider.get_config()
        
        assert config.temperature == 0.7
        assert config.max_tokens == 1500
    
    def test_default_config_max(self):
        """Тест дефолтной конфигурации max."""
        provider = GigaChatProvider(version="max")
        config = provider.get_config()
        
        assert config.temperature == 0.5
        assert config.max_tokens == 2000


class TestVLLMProvider:
    """Тесты для VLLMProvider."""
    
    def test_provider_creation(self):
        """Тест создания провайдера."""
        provider = VLLMProvider()
        
        assert provider.name == "vllm"
    
    def test_provider_with_custom_url(self):
        """Тест создания с кастомным URL."""
        provider = VLLMProvider(base_url="http://custom:8080/v1")
        
        assert provider._base_url == "http://custom:8080/v1"
    
    def test_set_parameters(self):
        """Тест изменения параметров."""
        provider = VLLMProvider()
        provider.set_parameters(temperature=0.5, max_tokens=500)
        
        config = provider.get_config()
        assert config.temperature == 0.5
        assert config.max_tokens == 500


# ============================================
# Integration Tests (mocked)
# ============================================

class TestModelIntegration:
    """Интеграционные тесты с моками."""
    
    @pytest.mark.asyncio
    async def test_generate_with_mock_provider(self):
        """Тест генерации через mock провайдер."""
        provider = MockModelProvider()
        
        response = await provider.generate("Тестовый запрос")
        
        assert response.content is not None
        assert len(response.content) > 0
        assert response.model_name == "mock_model"
    
    @pytest.mark.asyncio
    async def test_stream_with_mock_provider(self):
        """Тест стриминга через mock провайдер."""
        provider = MockModelProvider()
        
        chunks = []
        async for chunk in provider.stream("Test stream"):
            chunks.append(chunk)
        
        assert len(chunks) > 0
        assert chunks[-1].is_final
    
    @pytest.mark.asyncio
    async def test_availability_check(self):
        """Тест проверки доступности."""
        provider = MockModelProvider()
        
        assert await provider.is_available() is True
        
        provider.set_available(False)
        assert await provider.is_available() is False


# ============================================
# Comparative Test
# ============================================

class TestModelComparison:
    """Сравнительные тесты моделей."""
    
    def test_all_models_have_same_interface(self):
        """Все модели имеют одинаковый интерфейс."""
        providers = [
            GigaChatProvider(version="base"),
            GigaChatProvider(version="pro"),
            GigaChatProvider(version="max"),
            VLLMProvider()
        ]
        
        for provider in providers:
            # Проверяем наличие всех обязательных методов
            assert hasattr(provider, 'generate')
            assert hasattr(provider, 'stream')
            assert hasattr(provider, 'get_config')
            assert hasattr(provider, 'set_parameters')
            assert hasattr(provider, 'is_available')
            assert hasattr(provider, 'name')
            assert hasattr(provider, 'model_name')
    
    def test_all_models_return_correct_response_format(self):
        """Все модели возвращают правильный формат конфигурации."""
        providers = [
            GigaChatProvider(version="base"),
            GigaChatProvider(version="pro"),
            GigaChatProvider(version="max"),
            VLLMProvider()
        ]
        
        for provider in providers:
            config = provider.get_config()
            
            assert isinstance(config, ModelConfig)
            assert config.model_name is not None
            assert 0 <= config.temperature <= 1
            assert config.max_tokens > 0
