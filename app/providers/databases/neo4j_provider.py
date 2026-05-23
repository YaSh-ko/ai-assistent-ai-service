from typing import Any, Dict, List, Optional
from neo4j import GraphDatabase, AsyncGraphDatabase
from neo4j.exceptions import Neo4jError
from app.core.interfaces.i_graph_database import IGraphDatabase
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class Neo4jProvider(IGraphDatabase):
    """
    Neo4j implementation of the IGraphDatabase interface.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Neo4j driver using configuration settings.
        """
        if config:
            self.uri = config.get("neo4j_uri") or settings.NEO4J_URI
            self.user = config.get("neo4j_user") or settings.NEO4J_USERNAME
            self.password = config.get("neo4j_password") or settings.NEO4J_PASSWORD
        else:
            self.uri = settings.NEO4J_URI
            self.user = settings.NEO4J_USERNAME
            self.password = settings.NEO4J_PASSWORD
        
        if not self.uri or not self.user or not self.password:
            logger.warning("Neo4j configuration is missing. Graph database features will be disabled.")
            self.driver = None
            return

        try:
            self.driver = AsyncGraphDatabase.driver(self.uri, auth=(self.user, self.password))
            logger.info("Neo4j driver initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Neo4j driver: {e}")
            self.driver = None

    async def execute_read(self, query: str, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute a read-only query against the graph database.
        """
        if not self.driver:
            raise ConnectionError("Neo4j driver is not initialized.")

        try:
            async with self.driver.session() as session:
                result = await session.execute_read(self._execute_query_tx, query, parameters)
                return result
        except Exception as e:
            logger.error(f"Error executing read query: {e}")
            raise

    async def execute_write(self, query: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a write query against the graph database.
        """
        if not self.driver:
            raise ConnectionError("Neo4j driver is not initialized.")

        try:
            async with self.driver.session() as session:
                summary = await session.execute_write(self._execute_write_tx, query, parameters)
                return summary
        except Exception as e:
            logger.error(f"Error executing write query: {e}")
            raise

    async def close(self) -> None:
        """
        Close the connection to the graph database.
        """
        if self.driver:
            await self.driver.close()
            logger.info("Neo4j driver closed.")

    async def health_check(self) -> bool:
        """
        Check the health of the connection to the graph database.
        """
        if not self.driver:
            return False

        try:
            # Simple query to check connection with timeout
            import asyncio
            async with asyncio.timeout(3.0):
                await self.execute_read("RETURN 1 AS ping", {})
            return True
        except Exception as e:
            logger.error(f"Neo4j health check failed: {e}")
            return False

    async def _execute_query_tx(self, tx, query: str, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Helper method to execute a query within a transaction and return a list of dicts.
        """
        result = await tx.run(query, parameters)
        records = await result.data()
        return records

    async def _execute_write_tx(self, tx, query: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Helper method to execute a write query within a transaction and return summary.
        """
        result = await tx.run(query, parameters)
        # Consume the result to get summary
        summary = await result.consume()
        return {
            "nodes_created": summary.counters.nodes_created,
            "relationships_created": summary.counters.relationships_created,
            "properties_set": summary.counters.properties_set,
            "nodes_deleted": summary.counters.nodes_deleted,
            "relationships_deleted": summary.counters.relationships_deleted,
        }
