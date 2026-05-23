"""
API endpoints для управления моделями.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.factory.model_factory import ModelFactory
from app.services.llm_service import LLMService
from app.monitoring.metrics import ModelMetrics
from app.monitoring.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/models", tags=["Models"])

# Request/Response models
class SelectModelRequest(BaseModel):
    model_name: str = Field(..., description="Имя модели для выбора")


class ConfigUpdateRequest(BaseModel):
    temperature: Optional[float] = Field(None, ge=0.0, le=1.0, description="Температура генерации")
    max_tokens: Optional[int] = Field(None, gt=0, description="Максимальное количество токенов")
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="Top-p sampling")


class TestModelRequest(BaseModel):
    model_name: Optional[str] = Field(None, description="Имя модели для тестирования")
    prompt: str = Field(default="Привет! Ответь кратко.", description="Тестовый промпт")


class ModelInfo(BaseModel):
    name: str
    is_current: bool
    is_available: Optional[bool] = None
    config: dict


class ModelResponse(BaseModel):
    content: str
    model_name: str
    tokens_used: int
    latency_ms: float


# Endpoints
@router.get("", summary="Список моделей")
async def get_models():
    """
    Получить список всех доступных моделей с их конфигурациями.
    """
    models_info = ModelFactory.get_models_info()
    
    # Проверяем доступность
    availability = await ModelFactory.check_availability()
    
    result = []
    for model in models_info:
        model["is_available"] = availability.get(model["name"], False)
        result.append(model)
    
    return {
        "models": result,
        "current_model": ModelFactory.get_current_model()
    }


@router.get("/current", summary="Текущая модель")
async def get_current_model():
    """
    Получить информацию о текущей активной модели.
    """
    current = ModelFactory.get_current_model()
    provider = ModelFactory.get_model(current)
    config = provider.get_config()
    
    is_available = await provider.is_available()
    
    return {
        "name": current,
        "model_name": provider.model_name,
        "is_available": is_available,
        "config": config.to_dict()
    }


@router.post("/select", summary="Выбор модели")
async def select_model(request: SelectModelRequest):
    """
    Выбрать модель по имени.
    Модель станет текущей по умолчанию.
    """
    model_name = request.model_name.lower()
    
    if model_name not in ModelFactory.get_available_models():
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model: {model_name}. Available: {ModelFactory.get_available_models()}"
        )
    
    # Проверяем доступность
    provider = ModelFactory.get_model(model_name)
    is_available = await provider.is_available()
    
    if not is_available:
        raise HTTPException(
            status_code=503,
            detail=f"Model {model_name} is not available"
        )
    
    # Устанавливаем как текущую
    ModelFactory.set_current_model(model_name)
    
    logger.info(f"Model switched to: {model_name}")
    
    return {
        "message": f"Model switched to {model_name}",
        "current_model": model_name
    }


@router.patch("/config", summary="Изменение параметров")
async def update_model_config(request: ConfigUpdateRequest):
    """
    Изменить параметры текущей модели.
    """
    current = ModelFactory.get_current_model()
    provider = ModelFactory.get_model(current)
    
    # Применяем изменения
    provider.set_parameters(
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        top_p=request.top_p
    )
    
    new_config = provider.get_config()
    
    logger.info(f"Model {current} config updated")
    
    return {
        "message": "Configuration updated",
        "model": current,
        "config": new_config.to_dict()
    }


@router.post("/test", summary="Тестовый запрос")
async def test_model(request: TestModelRequest):
    """
    Отправить тестовый запрос к модели.
    """
    llm_service = LLMService()
    
    try:
        response = await llm_service.generate_response(
            prompt=request.prompt,
            model_name=request.model_name
        )
        
        return {
            "success": True,
            "response": {
                "content": response.content,
                "model_name": response.model_name,
                "tokens_used": response.tokens_used,
                "latency_ms": round(response.latency_ms, 2)
            }
        }
        
    except Exception as e:
        logger.error(f"Test request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics", summary="Метрики моделей")
async def get_metrics():
    """
    Получить метрики использования моделей.
    """
    metrics = ModelMetrics()
    
    return {
        "stats": metrics.get_all_stats(),
        "usage": metrics.get_usage_by_model(),
        "recent_requests": metrics.get_recent_requests(limit=20)
    }


@router.get("/metrics/prometheus", summary="Метрики в формате Prometheus")
async def get_prometheus_metrics():
    """
    Экспорт метрик в формате Prometheus.
    """
    from fastapi.responses import PlainTextResponse
    
    metrics = ModelMetrics()
    return PlainTextResponse(
        content=metrics.to_prometheus_format(),
        media_type="text/plain"
    )


@router.post("/cache/clear", summary="Очистка кеша")
async def clear_cache(model_name: Optional[str] = Query(None)):
    """
    Очистить кеш провайдеров моделей.
    """
    ModelFactory.clear_cache(model_name)
    
    return {
        "message": f"Cache cleared for: {model_name or 'all models'}"
    }
