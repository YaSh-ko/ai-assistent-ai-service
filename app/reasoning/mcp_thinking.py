from typing import Any, Dict, Optional
from app.reasoning.base_reasoning import BaseReasoning


class MCPThinking(BaseReasoning):
    """
    MCP (Model Context Protocol) thinking implementation.
    Reserved for future integration with an external MCP server.
    """

    async def _perform_reasoning(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        raise NotImplementedError(
            "MCPThinking is not yet implemented. "
            "Integrate an MCP server and implement this method."
        )
