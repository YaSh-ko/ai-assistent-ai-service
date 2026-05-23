from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from app.reasoning.types import ReasoningResult, ReasoningStep

class IReasoningEngine(ABC):
    """Interface for reasoning engines."""

    @abstractmethod
    async def reason(
        self, 
        query: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ReasoningResult:
        """
        Perform reasoning based on query and context.
        
        Args:
            query: The input query or question
            context: Optional context data
            **kwargs: Additional parameters
            
        Returns:
            ReasoningResult containing the answer and execution details
        """
        pass

    @abstractmethod
    def get_reasoning_steps(self) -> List[ReasoningStep]:
        """Get the list of reasoning steps executed so far."""
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata about the reasoning engine."""
        pass
