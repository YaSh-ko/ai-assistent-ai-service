"""
LLM Service - сервисный слой для работы с LLM моделями.
Обеспечивает унифицированный интерфейс для генерации ответов.
"""

from typing import Any, AsyncGenerator, Dict, Optional

from app.factory.model_factory import ModelFactory
from app.core.model_selector import ModelSelector
from app.interfaces.model_provider import (
    IModelProvider,
    ModelResponse,
    StreamChunk,
    ModelError
)
from app.services.context_service import ContextService
from app.services.session_service import SessionService
from app.monitoring.logger import get_logger
from app.monitoring.metrics import ModelMetrics
from app.services.billing import billing_service

logger = get_logger(__name__)


class LLMService:
    """
    Сервис для работы с LLM моделями.
    Предоставляет методы для генерации, стриминга и автовыбора моделей.
    """
    
    def __init__(
        self,
        context_service: Optional[ContextService] = None,
        session_service: Optional[SessionService] = None
    ):
        """
        Инициализация LLM сервиса.
        
        Args:
            context_service: Сервис для работы с контекстом
            session_service: Сервис для работы с сессиями
        """
        self._context_service = context_service or ContextService()
        self._session_service = session_service
        self._metrics = ModelMetrics()
    
    async def generate_response(
        self,
        prompt: str,
        model_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        **params
    ) -> ModelResponse:
        """
        Генерация ответа с указанной моделью.
        
        Args:
            prompt: Пользовательский промпт
            model_name: Имя модели (если None - используется текущая)
            system_prompt: Системный промпт
            session_id: ID сессии для контекста
            **params: Дополнительные параметры (temperature, max_tokens, и т.д.)
            
        Returns:
            ModelResponse с результатом генерации
        """
        logger.info(f"Generating response with model: {model_name or 'default'}")
        
        try:
            provider = ModelFactory.get_model(model_name)
            
            response = await provider.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                session_id=session_id,
                **params
            )
            
            # Write metrics and cost to Prometheus
            billing_service.record(
                model=response.model_name,
                input_tokens=response.prompt_tokens,
                output_tokens=response.completion_tokens
            )
            
            return response
            
        except ModelError as e:
            logger.error(f"Model error during generation: {e}")
            raise
    
    async def stream_response(
        self,
        prompt: str,
        model_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        **params
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Стриминг ответа с указанной моделью.
        
        Args:
            prompt: Пользовательский промпт
            model_name: Имя модели (если None - используется текущая)
            system_prompt: Системный промпт
            session_id: ID сессии для контекста
            **params: Дополнительные параметры
            
        Yields:
            StreamChunk с частями ответа
        """
        logger.info(f"Starting stream with model: {model_name or 'default'}")
        
        try:
            provider = ModelFactory.get_model(model_name)
            
            async for chunk in provider.stream(
                prompt=prompt,
                system_prompt=system_prompt,
                session_id=session_id,
                **params
            ):
                yield chunk
                
        except ModelError as e:
            logger.error(f"Model error during streaming: {e}")
            raise
    
    async def auto_select_and_generate(
        self,
        prompt: str,
        query_type: str = "simple_question",
        system_prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        **params
    ) -> ModelResponse:
        """
        Автоматический выбор модели на основе типа запроса через ModelSelector.
        
        Args:
            prompt: Пользовательский промпт
            query_type: Тип запроса (simple_question, dialogue, analysis, complex)
            system_prompt: Системный промпт
            session_id: ID сессии для контекста
            **params: Дополнительные параметры
            
        Returns:
            ModelResponse с результатом генерации
        """
        logger.info(f"Auto-selecting model for query type: {query_type}")
        
        # Получаем модель через ModelSelector
        provider = ModelSelector.get_model(query_type)
        
        response = await provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            session_id=session_id,
            **params
        )
        
        # Write metrics and cost to Prometheus
        billing_service.record(
            model=response.model_name,
            input_tokens=response.prompt_tokens,
            output_tokens=response.completion_tokens
        )
        
        return response
    
    async def generate_with_fallback(
        self,
        prompt: str,
        preferred_model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        **params
    ) -> ModelResponse:
        """
        Генерация с автоматическим fallback при недоступности модели.
        
        Args:
            prompt: Пользовательский промпт
            preferred_model: Предпочтительная модель
            system_prompt: Системный промпт
            session_id: ID сессии
            **params: Дополнительные параметры
            
        Returns:
            ModelResponse с результатом генерации
        """
        logger.info(f"Generating with fallback, preferred: {preferred_model or 'default'}")
        
        provider = await ModelFactory.get_model_with_fallback(preferred_model)
        
        response = await provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            session_id=session_id,
            **params
        )
        
        # Write metrics and cost to Prometheus
        billing_service.record(
            model=response.model_name,
            input_tokens=response.prompt_tokens,
            output_tokens=response.completion_tokens
        )
        
        return response
    
    async def generate_with_context(
        self,
        prompt: str,
        context_messages: list,
        model_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        **params
    ) -> ModelResponse:
        """
        Генерация ответа с включением контекста диалога.
        
        Args:
            prompt: Текущий промпт
            context_messages: История сообщений
            model_name: Имя модели
            system_prompt: Системный промпт
            session_id: ID сессии
            **params: Дополнительные параметры
            
        Returns:
            ModelResponse с результатом генерации
        """
        # Форматируем контекст
        context = self._context_service.format_context(context_messages)
        
        # Добавляем контекст к промпту
        full_prompt = f"{context}\n\nUser: {prompt}"
        
        return await self.generate_response(
            prompt=full_prompt,
            model_name=model_name,
            system_prompt=system_prompt,
            session_id=session_id,
            **params
        )
    
    def get_current_model(self) -> str:
        """Получить имя текущей модели."""
        return ModelFactory.get_current_model()
    
    def set_current_model(self, model_name: str) -> None:
        """Установить текущую модель."""
        ModelFactory.set_current_model(model_name)
    
    def get_available_models(self) -> list:
        """Получить список доступных моделей."""
        return ModelFactory.get_available_models()
    
    async def check_models_availability(self) -> Dict[str, bool]:
        """Проверить доступность всех моделей."""
        return await ModelFactory.check_availability()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Получить метрики использования моделей."""
        return self._metrics.get_all_stats()
    
    # Legacy метод для обратной совместимости
    async def generate(
        self, 
        prompt: str, 
        task_type: str = "simple_question", 
        **kwargs
    ) -> str:
        """Legacy метод - возвращает только текст ответа."""
        response = await self.auto_select_and_generate(
            prompt=prompt,
            query_type=task_type,
            **kwargs
        )
        return response.content
