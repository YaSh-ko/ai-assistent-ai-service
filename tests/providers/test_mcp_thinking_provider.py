import pytest

from app.providers.reasoning.mcp_thinking_provider import MCPThinkingProvider


@pytest.mark.asyncio
async def test_mcp_provider_reason_raises_not_implemented():
    provider = MCPThinkingProvider()

    with pytest.raises(NotImplementedError, match="MCPThinkingProvider is not yet implemented"):
        await provider.reason("query", {"ctx": "value"})


def test_mcp_provider_steps_and_metadata():
    provider = MCPThinkingProvider()

    assert provider.get_reasoning_steps() == []
    assert provider.get_metadata() == {
        "type": "MCPThinkingProvider",
        "status": "not_implemented",
    }

