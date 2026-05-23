from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class IGraphDatabase(ABC):
    """Interface for graph databases."""

    @abstractmethod
    async def query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query."""
        pass

    @abstractmethod
    async def add_node(self, label: str, properties: Dict[str, Any]) -> None:
        """Add a node to the graph."""
        pass

    @abstractmethod
    async def add_edge(
        self, 
        source_label: str, 
        source_props: Dict[str, Any],
        target_label: str, 
        target_props: Dict[str, Any],
        relation_type: str,
        relation_props: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add an edge between two nodes."""
        pass
