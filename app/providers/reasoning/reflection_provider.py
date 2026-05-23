from typing import Any, Dict, List, Optional
from app.interfaces.reasoning_engine import IReasoningEngine
from app.interfaces.model_provider import IModelProvider
from app.reasoning.reflection_reasoning import ReflectionReasoning
from app.reasoning.types import ReasoningResult, ReasoningStep
from app.core.config import settings

class ReflectionProvider(IReasoningEngine):
    """
    Провайдер для Reflection/Critic Loops рассуждения.
    Обеспечивает интеграцию ReflectionReasoning в систему, обрабатывая конфигурацию и зависимости.
    """
    
    def __init__(
        self, 
        model_provider: IModelProvider,
        dal: Any = None,  # Placeholder for DataAccessLayer
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Инициализация провайдера.
        
        Args:
            model_provider: Провайдер LLM.
            dal: Слой доступа к данным (опционально).
            config: Конфигурация движка.
        """
        self.config = config or settings.REFLECTION_CONFIG
        self.engine = ReflectionReasoning(
            model_provider=model_provider,
            config=self.config
        )
        # Inject DAL if needed in future
        # self.engine.dal = dal

    async def reason(
        self, 
        query: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ReasoningResult:
        """
        Выполняет рассуждение, делегируя вызов движку ReflectionReasoning.
        
        Args:
            query: Вопрос пользователя.
            context: Контекст.
            
        Returns:
            Результат рассуждения.
        """
        return await self.engine.reason(query, context, **kwargs)

    def get_reasoning_steps(self) -> List[ReasoningStep]:
        """Возвращает список шагов рассуждения последнего выполнения."""
        return self.engine.get_reasoning_steps()

    def get_metadata(self) -> Dict[str, Any]:
        """Возвращает метаданные движка."""
        return self.engine.get_metadata()
