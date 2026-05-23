import pytest

from app.reasoning.mcp_thinking import MCPThinking


@pytest.mark.asyncio
async def test_mcp_thinking_raises_not_implemented():
    reasoning = MCPThinking()

    with pytest.raises(NotImplementedError, match="MCPThinking is not yet implemented"):
        await reasoning._perform_reasoning("query", {"ctx": "value"})

