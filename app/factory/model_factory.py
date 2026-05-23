"""
Фабрика моделей для создания и управления LLM провайдерами.
Поддерживает кеширование и fallback-логику.
"""

from typing import Dict, List, Optional, Type
from threading import Lock

from app.interfaces.model_provider import (
    IModelProvider,
    ModelError,
    ModelUnavailableError
)
from app.providers.models.vllm_provider import VLLMProvider
from app.providers.models.gigachat_provider import GigaChatProvider
from app.core.config import settings
from app.monitoring.logger import get_logger

logger = get_logger(__name__)


class ModelFactory:
    """
    Фабрика для создания и управления LLM провайдерами.
    Поддерживает кеширование провайдеров и fallback при недоступности.
    """
    
    # Синглтон кеш провайдеров
    _providers_cache: Dict[str, IModelProvider] = {}
    _lock = Lock()
    
    # Порядок fallback моделей
    _fallback_order: List[str] = [
        "gigachat",
        "gigachat_pro",
        "gigachat_max",
        "vllm"
    ]
    
    # Текущая активная модель
    _current_model: Optional[str] = None
    
    @classmethod
    def get_model(cls, model_name: Optional[str] = None) -> IModelProvider:
        """
        Получить провайдер модели по имени.
        
        Args:
            model_name: Имя модели (vllm, gigachat, gigachat_pro, gigachat_max)
                       Если None, используется текущая модель из настроек
        
        Returns:
            Экземпляр IModelProvider
            
        Raises:
            ValueError: Если модель не найдена
        """
        if model_name is None:
            model_name = cls._current_model or settings.CURRENT_MODEL
        
        model_name = model_name.lower().replace("-", "_")
        
        with cls._lock:
            # Проверяем кеш
            if model_name in cls._providers_cache:
                logger.debug(f"Returning cached provider for {model_name}")
                return cls._providers_cache[model_name]
            
            # Создаём новый провайдер
            provider = cls._create_provider(model_name)
            
            # Кешируем
            cls._providers_cache[model_name] = provider
            
            return provider
    
    @classmethod
    def _create_provider(cls, model_name: str) -> IModelProvider:
        """Создание провайдера по имени модели."""
        logger.info(f"Creating provider for model: {model_name}")
        
        if model_name == "vllm":
            return VLLMProvider(
                base_url=settings.VLLM_CONFIG.get("base_url"),
                model_name=settings.VLLM_CONFIG.get("model_name"),
                temperature=settings.VLLM_CONFIG.get("temperature", 0.7),
                max_tokens=settings.VLLM_CONFIG.get("max_tokens", 2000)
            )
        
        elif model_name == "gigachat" or model_name == "gigachat_base":
            return GigaChatProvider(
                version="base",
                credentials=settings.GIGACHAT_CREDENTIALS,
                client_id=settings.GIGACHAT_CLIENT_ID,
                client_secret=settings.GIGACHAT_CLIENT_SECRET,
                scope=settings.GIGACHAT_SCOPE
            )
        
        elif model_name == "gigachat_pro":
            return GigaChatProvider(
                version="pro",
                credentials=settings.GIGACHAT_CREDENTIALS,
                client_id=settings.GIGACHAT_CLIENT_ID,
                client_secret=settings.GIGACHAT_CLIENT_SECRET,
                scope=settings.GIGACHAT_SCOPE
            )
        
        elif model_name == "gigachat_max":
            return GigaChatProvider(
                version="max",
                credentials=settings.GIGACHAT_CREDENTIALS,
                client_id=settings.GIGACHAT_CLIENT_ID,
                client_secret=settings.GIGACHAT_CLIENT_SECRET,
                scope=settings.GIGACHAT_SCOPE
            )
        
        else:
            raise ValueError(f"Unknown model: {model_name}. Available: {cls.get_available_models()}")
    
    @classmethod
    async def get_model_with_fallback(
        cls, 
        model_name: Optional[str] = None
    ) -> IModelProvider:
        """
        Получить провайдер с автоматическим fallback при недоступности.
        
        Args:
            model_name: Предпочтительная модель
            
        Returns:
            Первый доступный провайдер
            
        Raises:
            ModelUnavailableError: Если все модели недоступны
        """
        preferred_model = model_name or settings.CURRENT_MODEL
        
        # Строим порядок для fallback, начиная с предпочтительной модели
        fallback_order = [preferred_model]
        for model in cls._fallback_order:
            if model not in fallback_order:
                fallback_order.append(model)
        
        # Пробуем каждую модель
        for candidate in fallback_order:
            try:
                provider = cls.get_model(candidate)
                
                if await provider.is_available():
                    if candidate != preferred_model:
                        logger.warning(
                            f"Using fallback model {candidate} instead of {preferred_model}"
                        )
                    return provider
                else:
                    logger.warning(f"Model {candidate} is not available")
                    
            except Exception as e:
                logger.warning(f"Failed to get model {candidate}: {e}")
                continue
        
        raise ModelUnavailableError(
            "all_models",
            "All models are unavailable"
        )
    
    @classmethod
    def get_available_models(cls) -> List[str]:
        """Получить список доступных моделей."""
        return ["vllm", "gigachat", "gigachat_pro", "gigachat_max"]
    
    @classmethod
    async def check_availability(cls) -> Dict[str, bool]:
        """
        Проверить доступность всех моделей.
        
        Returns:
            Словарь {model_name: is_available}
        """
        result = {}
        
        for model_name in cls.get_available_models():
            try:
                provider = cls.get_model(model_name)
                result[model_name] = await provider.is_available()
            except Exception as e:
                logger.warning(f"Error checking {model_name}: {e}")
                result[model_name] = False
        
        return result
    
    @classmethod
    def set_current_model(cls, model_name: str) -> None:
        """
        Установить текущую модель по умолчанию.
        
        Args:
            model_name: Имя модели
            
        Raises:
            ValueError: Если модель не существует
        """
        model_name = model_name.lower()
        
        if model_name not in cls.get_available_models():
            raise ValueError(f"Unknown model: {model_name}")
        
        logger.info(f"Setting current model to: {model_name}")
        cls._current_model = model_name
    
    @classmethod
    def get_current_model(cls) -> str:
        """Получить имя текущей модели."""
        return cls._current_model or settings.CURRENT_MODEL
    
    @classmethod
    def get_models_info(cls) -> List[Dict]:
        """
        Получить информацию обо всех моделях.
        
        Returns:
            Список словарей с информацией о моделях
        """
        models_info = []
        
        for model_name in cls.get_available_models():
            config = settings.get_model_config(model_name)
            
            models_info.append({
                "name": model_name,
                "is_current": model_name == cls.get_current_model(),
                "config": config,
                "cached": model_name in cls._providers_cache
            })
        
        return models_info
    
    @classmethod
    def clear_cache(cls, model_name: Optional[str] = None) -> None:
        """
        Очистить кеш провайдеров.
        
        Args:
            model_name: Имя модели для очистки, или None для полной очистки
        """
        with cls._lock:
            if model_name:
                if model_name in cls._providers_cache:
                    del cls._providers_cache[model_name]
                    logger.info(f"Cleared cache for model: {model_name}")
            else:
                cls._providers_cache.clear()
                logger.info("Cleared all model caches")

    @classmethod
    async def close_all(cls) -> None:
        """Закрыть все активные провайдеры и очистить кеш."""
        with cls._lock:
            for model_name, provider in cls._providers_cache.items():
                try:
                    await provider.close()
                    logger.info(f"Closed provider for {model_name}")
                except Exception as e:
                    logger.error(f"Error closing provider {model_name}: {e}")
            
            cls._providers_cache.clear()
            logger.info("All model providers closed")

    # Legacy метод для обратной совместимости
    @staticmethod
    def create_model(provider_type: str) -> IModelProvider:
        """Legacy метод - использует get_model()."""
        return ModelFactory.get_model(provider_type)
