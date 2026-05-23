"""
Интерфейс для LLM провайдеров.
Определяет единый контракт для всех моделей (vLLM, GigaChat, и др.)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional
from enum import Enum
import time


class ModelVersion(Enum):
    """Версии моделей GigaChat."""
    BASE = "base"
    PRO = "pro"
    MAX = "max"


@dataclass
class ModelConfig:
    """Конфигурация модели."""
    model_name: str
    temperature: float = 0.7
    max_tokens: int = 2000
    top_p: float = 0.9
    timeout: int = 30
    retry_attempts: int = 3
    extra_params: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь."""
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "timeout": self.timeout,
            "retry_attempts": self.retry_attempts,
            **self.extra_params
        }


@dataclass
class ModelResponse:
    """Единый формат ответа от всех моделей."""
    content: str
    model_name: str
    tokens_used: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    finish_reason: str = "stop"
    raw_response: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_error(cls, error: Exception, model_name: str) -> "ModelResponse":
        """Создать ответ из ошибки."""
        return cls(
            content=f"Error: {str(error)}",
            model_name=model_name,
            finish_reason="error"
        )


@dataclass
class StreamChunk:
    """Чанк для стриминга."""
    content: str
    is_final: bool = False
    model_name: str = ""
    finish_reason: Optional[str] = None


class ModelError(Exception):
    """Базовое исключение для ошибок модели."""
    def __init__(self, message: str, model_name: str, retry_possible: bool = True):
        self.message = message
        self.model_name = model_name
        self.retry_possible = retry_possible
        super().__init__(message)


class ModelUnavailableError(ModelError):
    """Исключение когда модель недоступна."""
    def __init__(self, model_name: str, reason: str = "Model is unavailable"):
        super().__init__(reason, model_name, retry_possible=False)


class RateLimitError(ModelError):
    """Исключение при rate limit."""
    def __init__(self, model_name: str, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        message = "Rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after}s"
        super().__init__(message, model_name, retry_possible=True)


class TimeoutError(ModelError):
    """Исключение при таймауте."""
    def __init__(self, model_name: str, timeout: int):
        super().__init__(f"Request timed out after {timeout}s", model_name, retry_possible=True)


class IModelProvider(ABC):
    """Интерфейс для LLM провайдеров."""
    
    @abstractmethod
    async def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs
    ) -> ModelResponse:
        """
        Генерация ответа от модели.
        
        Args:
            prompt: Пользовательский промпт
            system_prompt: Системный промпт (опционально)
            session_id: ID сессии для контекста (опционально)
            **kwargs: Дополнительные параметры модели
            
        Returns:
            ModelResponse с результатом генерации
        """
        pass

    @abstractmethod
    async def stream(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Стриминг токенов от модели.
        
        Args:
            prompt: Пользовательский промпт
            system_prompt: Системный промпт (опционально)
            session_id: ID сессии для контекста (опционально)
            **kwargs: Дополнительные параметры модели
            
        Yields:
            StreamChunk с частями ответа
        """
        pass
    
    @abstractmethod
    def get_config(self) -> ModelConfig:
        """
        Получение текущей конфигурации модели.
        
        Returns:
            ModelConfig с текущими параметрами
        """
        pass
    
    @abstractmethod
    def set_parameters(
        self,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        **kwargs
    ) -> None:
        """
        Изменение параметров модели.
        
        Args:
            temperature: Температура генерации (0.0-1.0)
            max_tokens: Максимальное количество токенов
            top_p: Top-p sampling параметр
            **kwargs: Дополнительные параметры
        """
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """
        Проверка доступности модели.
        
        Returns:
            True если модель доступна и готова к работе
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Закрытие ресурсов провайдера."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Имя провайдера модели."""
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Имя конкретной модели."""
        pass


class BaseModelProvider(IModelProvider):
    """Базовый класс для провайдеров с общей функциональностью."""
    
    def __init__(self, config: ModelConfig):
        self._config = config
        self._is_initialized = False
    
    def get_config(self) -> ModelConfig:
        return self._config
    
    def set_parameters(
        self,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        **kwargs
    ) -> None:
        if temperature is not None:
            if not 0.0 <= temperature <= 1.0:
                raise ValueError("temperature must be between 0.0 and 1.0")
            self._config.temperature = temperature
        
        if max_tokens is not None:
            if max_tokens <= 0:
                raise ValueError("max_tokens must be positive")
            self._config.max_tokens = max_tokens
        
        if top_p is not None:
            if not 0.0 <= top_p <= 1.0:
                raise ValueError("top_p must be between 0.0 and 1.0")
            self._config.top_p = top_p
        
        # Обновление дополнительных параметров
        for key, value in kwargs.items():
            self._config.extra_params[key] = value
    
    async def close(self) -> None:
        """По умолчанию ничего не делаем."""
        pass

    def _measure_latency(self, start_time: float) -> float:
        """Вычисление latency в миллисекундах."""
        return (time.time() - start_time) * 1000
    
    @property
    def model_name(self) -> str:
        return self._config.model_name
