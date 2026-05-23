import pytest

from app.reasoning.cot_reasoning import CoTReasoning
from app.reasoning.mcp_thinking import MCPThinking
from app.reasoning.reasoning_strategies import ReasoningStrategies
from app.reasoning.reflection_reasoning import ReflectionReasoning


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("cot", CoTReasoning),
        ("reflection", ReflectionReasoning),
        ("mcp_thinking", MCPThinking),
    ],
)
def test_get_strategy_success(name, expected):
    assert ReasoningStrategies.get_strategy(name) is expected


def test_get_strategy_unknown_raises():
    with pytest.raises(ValueError, match="Unknown reasoning strategy 'unknown'"):
        ReasoningStrategies.get_strategy("unknown")

