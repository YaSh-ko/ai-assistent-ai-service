import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from app.reasoning.cot_reasoning import CoTReasoning
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
            content="Mock response content",
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
    print("Testing CoTReasoning implementation...")
    
    mock_provider = MockModelProvider()
    engine = CoTReasoning(model_provider=mock_provider)
    
    query = "What happened yesterday?"
    print(f"Query: {query}")
    
    result = await engine.reason(query)
    
    print("\nResult:")
    print(f"Answer: {result['answer']}")
    print(f"Status: {result['status']}")
    print(f"Total Duration: {result['total_duration_ms']:.2f}ms")
    print(f"Steps: {len(result['steps'])}")
    
    for step in result['steps']:
        print(f"  - Step {step['step_number']}: {step['description']} ({step['duration_ms']:.2f}ms)")
        
    assert result['status'] == ReasoningStatus.COMPLETED
    assert len(result['steps']) == 4
    
    # Check metrics
    stats = engine.metrics.get_stats()
    print("\nMetrics:")
    print(stats)
    assert stats['total_executions'] >= 1
    
    print("\nVerification successful!")

if __name__ == "__main__":
    asyncio.run(main())
