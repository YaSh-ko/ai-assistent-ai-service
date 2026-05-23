import time
import logging
from abc import abstractmethod
from typing import Any, Dict, List, Optional
from app.interfaces.reasoning_engine import IReasoningEngine
from app.reasoning.types import ReasoningResult, ReasoningStep, ReasoningStatus

logger = logging.getLogger(__name__)

class BaseReasoning(IReasoningEngine):
    """
    Base class for reasoning engines providing common functionality
    like logging, timing, and error handling.
    """

    def __init__(self):
        self._steps: List[ReasoningStep] = []
        self._metadata: Dict[str, Any] = {
            "type": self.__class__.__name__,
            "version": "1.0.0"
        }

    async def reason(
        self, 
        query: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ReasoningResult:
        """
        Template method for reasoning process.
        Handles common logic like timing, error catching, and result formatting.
        """
        start_time = time.time()
        self._steps = []  # Reset steps for new reasoning request
        
        logger.info(f"Starting reasoning with {self.__class__.__name__} for query: {query}")
        
        try:
            # Validate input
            self._validate_input(query, context)
            
            # Execute specific reasoning logic
            answer = await self._perform_reasoning(query, context, **kwargs)
            
            status = ReasoningStatus.COMPLETED
            error = None
            
        except Exception as e:
            logger.error(f"Reasoning failed: {str(e)}", exc_info=True)
            status = ReasoningStatus.FAILED
            error = str(e)
            answer = None
            
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        
        result: ReasoningResult = {
            "answer": answer,
            "steps": self._steps,
            "total_duration_ms": duration_ms,
            "total_tokens": self._calculate_total_tokens(),
            "metadata": {
                **self._metadata,
                "timestamp": start_time
            },
            "status": status,
            "error": error
        }
        
        logger.info(f"Reasoning finished in {duration_ms:.2f}ms with status: {status}")
        return result

    @abstractmethod
    async def _perform_reasoning(
        self, 
        query: str, 
        context: Optional[Dict[str, Any]],
        **kwargs
    ) -> Any:
        """
        Abstract method to be implemented by specific reasoning strategies.
        Should return the final answer.
        """
        pass

    def get_reasoning_steps(self) -> List[ReasoningStep]:
        return self._steps

    def get_metadata(self) -> Dict[str, Any]:
        return self._metadata

    def _add_step(self, step: ReasoningStep) -> None:
        """Helper to add a step and log it."""
        self._steps.append(step)
        logger.debug(f"Step {step['step_number']}: {step['action']} - {step['description']}")

    def _validate_input(self, query: str, context: Optional[Dict[str, Any]]) -> None:
        """Basic validation, can be overridden."""
        if not query:
            raise ValueError("Query cannot be empty")

    def _calculate_total_tokens(self) -> int:
        """
        Calculate total tokens used. 
        This is a placeholder, real implementation might sum tokens from steps.
        """
        return 0
