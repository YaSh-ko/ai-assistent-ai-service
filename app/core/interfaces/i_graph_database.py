from abc import ABC, abstractmethod
from typing import Any, Dict, List

class IGraphDatabase(ABC):
    """
    Interface for graph databases, defining a standard contract for interaction.
    Follows the Dependency Inversion Principle.
    """

    @abstractmethod
    async def execute_read(self, query: str, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute a read-only query against the graph database.

        Args:
            query (str): The Cypher query string to execute.
            parameters (Dict[str, Any]): A dictionary of parameters to use in the query.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, where each dictionary represents a record returned by the query.

        Raises:
            Exception: If the query execution fails.
        """
        pass

    @abstractmethod
    async def execute_write(self, query: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a write query against the graph database.

        Args:
            query (str): The Cypher query string to execute.
            parameters (Dict[str, Any]): A dictionary of parameters to use in the query.

        Returns:
            Dict[str, Any]: A summary of the write operation (e.g., number of nodes created, relationships created).

        Raises:
            Exception: If the query execution fails.
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """
        Close the connection to the graph database.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check the health of the connection to the graph database.

        Returns:
            bool: True if the connection is healthy, False otherwise.
        """
        pass
