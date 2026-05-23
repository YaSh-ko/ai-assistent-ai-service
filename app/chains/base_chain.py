from typing import Any, Dict
from abc import ABC, abstractmethod

class BaseChain(ABC):
    """Base class for LangGraph chains."""
    
    @abstractmethod
    def build_graph(self) -> Any:
        pass
