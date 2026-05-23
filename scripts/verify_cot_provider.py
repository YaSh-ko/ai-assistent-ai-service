import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

# Mock pydantic and config before importing app modules that depend on them
from unittest.mock import MagicMock
sys.modules["pydantic"] = MagicMock()
sys.modules["pydantic_settings"] = MagicMock()

# Mock settings
mock_settings = MagicMock()
mock_settings.COT_CONFIG = {
    "max_reasoning_depth": 4,
    "max_clarifying_questions": 5,
    "enable_verification": True,
    "neo4j_max_depth": 3,
    "timeout_per_step": 30,
}
sys.modules["app.core.config"] = MagicMock()
sys.modules["app.core.config"].settings = mock_settings

from app.providers.reasoning.cot_provider import CoTProvider
from app.interfaces.model_provider import IModelProvider, ModelResponse
from app.reasoning.types import ReasoningStatus

class MockModelProvider(IModelProvider):
    @property
    def name(self) -> str:
        return "mock_provider"

    @property
    def model_name(self) -> str:
        return "mock_model"
        
    async def generate(self, prompt: str, **kwargs) -> ModelResponse:
        return ModelResponse(
            content="Mock response content. Can answer without context: True",
            model_name=self.model_name
        )
        
    async def stream(self, prompt: str, **kwargs):
        yield "Mock"
        
    def get_config(self):
        pass
        
    def set_parameters(self, **kwargs):
        pass
        
    async def is_available(self):
        return True

async def main():
    print("Testing CoTProvider implementation...")
    
    mock_provider = MockModelProvider()
    
    # Test with custom config
    config = {
        "max_reasoning_depth": 2,
        "enable_verification": True,
        "timeout_per_step": 5
    }
    
    provider = CoTProvider(model_provider=mock_provider, config=config)
    
    query = "What is the meaning of life?"
    print(f"Query: {query}")
    
    result = await provider.reason(query)
    
    print("\nResult:")
    print(f"Answer: {result['answer']}")
    print(f"Status: {result['status']}")
    
    assert result['status'] == ReasoningStatus.COMPLETED
    assert len(result['steps']) == 4 # Understand, Plan, Execute, Verify
    
    # Verify metadata contains config
    metadata = provider.get_metadata()
    assert metadata['config'] == config
    
    print("\nVerification successful!")

if __name__ == "__main__":
    asyncio.run(main())
