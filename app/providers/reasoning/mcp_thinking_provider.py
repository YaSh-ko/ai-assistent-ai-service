from typing import Any, Dict, List, Optional
from app.interfaces.reasoning_engine import IReasoningEngine
from app.reasoning.types import ReasoningResult, ReasoningStep


class MCPThinkingProvider(IReasoningEngine):
    """
    Reasoning engine provider backed by MCP (Model Context Protocol).
    Reserved for future integration with an external MCP server.
    """

    async def reason(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ReasoningResult:
        raise NotImplementedError(
            "MCPThinkingProvider is not yet implemented. "
            "Integrate an MCP server and implement this method."
        )

    def get_reasoning_steps(self) -> List[ReasoningStep]:
        return []

    def get_metadata(self) -> Dict[str, Any]:
        return {"type": "MCPThinkingProvider", "status": "not_implemented"}
