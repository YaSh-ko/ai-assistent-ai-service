from app.reasoning.base_reasoning import BaseReasoning
from app.reasoning.cot_reasoning import CoTReasoning
from app.reasoning.reflection_reasoning import ReflectionReasoning
from app.reasoning.mcp_thinking import MCPThinking


class ReasoningStrategies:
    """Collection of reasoning strategies."""

    _REGISTRY = {
        "cot": CoTReasoning,
        "reflection": ReflectionReasoning,
        "mcp_thinking": MCPThinking,
    }

    @staticmethod
    def get_strategy(strategy_name: str) -> type[BaseReasoning]:
        """
        Return the reasoning class for the given strategy name.

        Args:
            strategy_name: One of 'cot', 'reflection', 'mcp_thinking'.

        Raises:
            ValueError: If the strategy name is not registered.
        """
        strategy_cls = ReasoningStrategies._REGISTRY.get(strategy_name)
        if strategy_cls is None:
            available = ", ".join(ReasoningStrategies._REGISTRY)
            raise ValueError(
                f"Unknown reasoning strategy '{strategy_name}'. "
                f"Available: {available}"
            )
        return strategy_cls
