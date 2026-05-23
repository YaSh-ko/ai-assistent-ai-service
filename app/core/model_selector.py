from typing import Dict, Any, Optional, Union
from app.models.complexity_models import ComplexityLevel, ModelSelectionResult, ComplexityResult
from app.core.complexity_classifier import get_complexity_classifier
from app.factory.model_factory import ModelFactory

class ModelSelector:
    """
    Selects the appropriate LLM model and parameters based on task complexity.
    """
    
    from app.core.config import settings

    MODELS = {
        "simple": "gigachat",
        "medium": "gigachat_pro",
        "complex": "gigachat_max"
    }
    
    PARAMS = {
        "simple": {
            "temperature": 0.3,
            "top_p": 0.5,
            "max_tokens": 500
        },
        "medium": {
            "temperature": 0.5,
            "top_p": 0.4,
            "max_tokens": 1500
        },
        "complex": {
            "temperature": 0.7,
            "top_p": 0.7,
            "max_tokens": 2000
        }
    }

    @staticmethod
    def select_model(query_or_complexity: str, prefer_privacy: bool = False, prefer_speed: bool = False) -> Union[str, Any]:
        """
        Selects model based on query or complexity.
        
        If input is a complexity level (simple, medium, complex), returns model name (string).
        If input is a query string, returns provider object (for backward compatibility with tests).
        """
        # Check if it's a complexity level
        if query_or_complexity in ["simple", "medium", "complex"]:
            return ModelSelector.MODELS.get(query_or_complexity, "gigachat_pro")
            
        # If it's a query, use classifier and return provider
        classifier = get_complexity_classifier()
        result = classifier.classify(query_or_complexity)
        
        model_name = result.suggested_model
        if prefer_privacy:
            model_name = "vllm"
            
        return ModelFactory.get_model(model_name)

    @staticmethod
    def select_model_with_details(query: str, prefer_privacy: bool = False, prefer_speed: bool = False) -> ModelSelectionResult:
        """Selects model and returns detailed result."""
        classifier = get_complexity_classifier()
        complexity = classifier.classify(query)
        
        model_name = complexity.suggested_model
        reason = complexity.reasoning
        
        if prefer_privacy:
            model_name = "vllm"
            reason = "Пользователь предпочел приватность, используем локальную модель."
            
        return ModelSelectionResult(
            model_name=model_name,
            complexity=complexity,
            reason=reason
        )

    @staticmethod
    def get_params(complexity: str) -> Dict[str, Any]:
        """Gets model parameters based on complexity."""
        return ModelSelector.PARAMS.get(complexity, ModelSelector.PARAMS["medium"])

    @staticmethod
    def get_model(model_type: str) -> Any:
        """Legacy method for getting model provider."""
        # Map legacy types to models
        mapping = {
            "simple_question": "gigachat",
            "analysis": "gigachat_pro",
            "complex": "gigachat_max"
        }
        model_name = mapping.get(model_type, model_type)
        return ModelFactory.get_model(model_name)

    @staticmethod
    def get_model_for_query(query: str) -> Any:
        """Legacy method for getting model provider for query."""
        return ModelSelector.select_model(query)

    @staticmethod
    def get_model_for_complexity(complexity: str | ComplexityLevel) -> Any:
        """Gets model provider based on complexity level."""
        level = complexity.value if isinstance(complexity, ComplexityLevel) else complexity
        model_name = ModelSelector.MODELS.get(level, "gigachat_pro")
        return ModelFactory.get_model(model_name)
