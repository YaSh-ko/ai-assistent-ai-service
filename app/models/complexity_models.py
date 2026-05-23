"""
Модели данных для классификации сложности запросов.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ComplexityLevel(str, Enum):
    """Уровни сложности запросов."""
    SIMPLE = "simple"      # → vLLM (локально) - приватность, скорость
    MEDIUM = "medium"      # → GigaChat Pro (API) - анализ, начало дневника
    COMPLEX = "complex"    # → GigaChat Max (API) - паттерны, глубокий анализ


class QueryContext(BaseModel):
    """Контекст запроса для более точной классификации."""
    thread_id: Optional[str] = None
    message_count: int = 0
    has_diary_entries: bool = False
    is_first_message: bool = True
    user_id: Optional[str] = None


class ComplexityResult(BaseModel):
    """Результат классификации сложности запроса."""
    level: ComplexityLevel
    confidence: float = Field(ge=0.0, le=1.0, description="Уверенность классификации 0.0-1.0")
    reasoning: str = Field(description="Объяснение выбора уровня сложности")
    suggested_model: str = Field(description="Предложенная модель")


class ModelSelectionRequest(BaseModel):
    """Запрос на выбор модели."""
    query: str
    context: Optional[QueryContext] = None
    prefer_privacy: bool = False
    prefer_speed: bool = False


class ModelSelectionResult(BaseModel):
    """Результат выбора модели."""
    model_name: str
    complexity: ComplexityResult
    reason: str
