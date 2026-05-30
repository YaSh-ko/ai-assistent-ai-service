from typing import Dict, Optional, Any
from app.interfaces.reasoning_engine import IReasoningEngine
from app.providers.reasoning.cot_provider import CoTProvider
from app.providers.reasoning.reflection_provider import ReflectionProvider
from app.core.config import settings
from app.factory.model_factory import ModelFactory

class ReasoningFactory:
    _instances: Dict[str, IReasoningEngine] = {}

    @classmethod
    def get_reasoning_engine(cls, engine_type: str = "cot") -> IReasoningEngine:
        """
        Get a reasoning engine instance by type.
        Uses lazy initialization and caching (singleton per type).
        """
        if engine_type not in cls._instances:
            if engine_type == "cot":
                cls._instances[engine_type] = cls.create_cot_provider()
            elif engine_type == "reflection":
                cls._instances[engine_type] = cls.create_reflection_provider()
            else:
                raise ValueError(f"Unknown reasoning engine type: {engine_type}")
        
        return cls._instances[engine_type]

    @classmethod
    def create_cot_provider(cls) -> CoTProvider:
        """Create a configured CoTProvider."""
        # Get dependencies
        # For now, we use the default model from ModelFactory. 
        # In a real scenario, we might want a specific model for reasoning.
        model_provider = ModelFactory.get_model(settings.CURRENT_MODEL)
        
        # Get config
        config = settings.REASONING_CONFIG.get("cot", settings.COT_CONFIG)
        
        return CoTProvider(
            model_provider=model_provider,
            config=config
        )

    @classmethod
    def create_reflection_provider(cls) -> ReflectionProvider:
        """Create a configured ReflectionProvider."""
        # Get dependencies
        model_provider = ModelFactory.get_model(settings.CURRENT_MODEL)
        
        # Get config
        config = settings.REASONING_CONFIG.get("reflection", settings.REFLECTION_CONFIG)
        
        return ReflectionProvider(
            model_provider=model_provider,
            config=config
        )
