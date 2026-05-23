import logging
import time
from typing import Any, Dict, Optional, List
from app.factory.reasoning_factory import ReasoningFactory
from app.core.config import settings
from app.utils.helpers import select_reasoning_engine
from app.monitoring.metrics import ReasoningMetrics
from app.interfaces.reasoning_engine import IReasoningEngine

logger = logging.getLogger(__name__)

class ReasoningService:
    """
    Сервис для управления движками рассуждения и оркестрации процесса Reasoning.
    
    Отвечает за:
    - Выбор подходящего движка (engine) на основе типа задачи.
    - Выполнение процесса рассуждения.
    - Сохранение истории рассуждений.
    - Инициализацию (warmup) движков при запуске.
    """
    
    def __init__(self):
        """Инициализация сервиса и метрик."""
        self.metrics = ReasoningMetrics()
        # In-memory cache for reasoning results (for demonstration/MVP)
        # In production, this should be a persistent store (Redis/Postgres)
        self._reasoning_history: Dict[str, Dict[str, Any]] = {}

    def select_engine(self, task_type: str, complexity: Optional[str] = None) -> IReasoningEngine:
        """
        Выбирает подходящий движок рассуждения на основе типа задачи и сложности.
        
        Args:
            task_type: Тип задачи (например, 'complex', 'simple_question').
            complexity: Сложность задачи (опционально).
            
        Returns:
            Экземпляр IReasoningEngine.
        """
        # Use helper to get engine name from config mapping
        engine_name = select_reasoning_engine(task_type)
        
        # If complexity is high, we might want to override or adjust
        # For now, we stick to the mapping logic
        
        try:
            return ReasoningFactory.get_reasoning_engine(engine_name)
        except Exception as e:
            logger.error(f"Failed to get engine '{engine_name}': {e}. Fallback to default.")
            default_engine = settings.REASONING_CONFIG.get("default_engine", "cot")
            return ReasoningFactory.get_reasoning_engine(default_engine)

    async def execute_reasoning(
        self, 
        question: str, 
        context: Optional[Dict[str, Any]] = None,
        task_type: str = "simple_question",
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Оркестрация процесса рассуждения.
        
        Args:
            question: Вопрос пользователя.
            context: Контекст для рассуждения (результаты поиска и т.д.).
            task_type: Тип задачи для выбора движка.
            user_id: ID пользователя.
            
        Returns:
            Словарь с результатом рассуждения (ответ, шаги, метаданные).
        """
        start_time = time.time()
        engine = self.select_engine(task_type)
        
        logger.info(f"Executing reasoning for user {user_id} with engine {engine.__class__.__name__}")
        
        try:
            result = await engine.reason(
                query=question,
                context=context
            )
            
            # Store history
            # We assume result has a 'metadata' field or we create an ID
            reasoning_id = f"reasoning_{int(time.time())}_{user_id}"
            
            # Enrich result with metadata if needed
            if isinstance(result, dict):
                result['reasoning_id'] = reasoning_id
            
            self._save_reasoning_info(reasoning_id, result, engine.__class__.__name__)
            
            elapsed = time.time() - start_time
            logger.info(f"Reasoning completed in {elapsed:.3f}s (engine={engine.__class__.__name__})")

            return result
            
        except Exception as e:
            logger.error(f"Reasoning execution failed: {e}", exc_info=True)
            # Fallback or re-raise
            # For now, return error structure
            return {
                "error": str(e),
                "status": "failed",
                "answer": "I apologize, but I encountered an error while processing your request."
            }

    def get_reasoning_info(self, reasoning_id: str) -> Optional[Dict[str, Any]]:
        """
        Возвращает информацию о прошедшем выполнении рассуждения.
        
        Args:
            reasoning_id: Уникальный ID рассуждения.
            
        Returns:
            Данные о рассуждении или None.
        """
        return self._reasoning_history.get(reasoning_id)

    def warmup(self) -> None:
        """
        Инициализирует движки рассуждения при запуске сервиса.
        Позволяет избежать задержек при первом запросе.
        """
        logger.info("Warming up reasoning service...")
        try:
            # Initialize default engine
            default_engine = settings.REASONING_CONFIG.get("default_engine", "cot")
            ReasoningFactory.get_reasoning_engine(default_engine)
            logger.info(f"Initialized default engine: {default_engine}")
            
            # Initialize other mapped engines if different
            mapping = settings.REASONING_CONFIG.get("task_mapping", {})
            for task, engine_name in mapping.items():
                if engine_name != default_engine:
                    ReasoningFactory.get_reasoning_engine(engine_name)
                    logger.info(f"Initialized engine for {task}: {engine_name}")
                    
        except Exception as e:
            logger.error(f"Warmup failed: {e}")

    def _save_reasoning_info(self, reasoning_id: str, result: Any, engine_name: str) -> None:
        """
        Сохраняет результат рассуждения в историю.
        
        Args:
            reasoning_id: ID рассуждения.
            result: Результат выполнения.
            engine_name: Имя использованного движка.
        """
        self._reasoning_history[reasoning_id] = {
            "id": reasoning_id,
            "timestamp": time.time(),
            "engine": engine_name,
            "result": result
        }
