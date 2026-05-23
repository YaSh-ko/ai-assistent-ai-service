import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from app.reasoning.base_reasoning import BaseReasoning
from app.reasoning.types import ReasoningResult, ReasoningStep, ReasoningStatus

class MockReasoningEngine(BaseReasoning):
    async def _perform_reasoning(self, query: str, context: dict, **kwargs):
        # Simulate a reasoning step
        self._add_step({
            "step_number": 1,
            "description": "Analyzing the query",
            "action": "analyze",
            "action_input": query,
            "observation": "Query is simple",
            "thought": "I should just return a simple answer",
            "duration_ms": 10.0,
            "status": ReasoningStatus.COMPLETED,
            "metadata": {}
        })
        
        # Simulate another step
        self._add_step({
            "step_number": 2,
            "description": "Generating answer",
            "action": "generate",
            "action_input": None,
            "observation": None,
            "thought": "The answer is 42",
            "duration_ms": 5.0,
            "status": ReasoningStatus.COMPLETED,
            "metadata": {}
        })
        
        return "42"

async def main():
    print("Testing BaseReasoning implementation...")
    engine = MockReasoningEngine()
    
    query = "What is the answer?"
    print(f"Query: {query}")
    
    result = await engine.reason(query)
    
    print("\nResult:")
    print(f"Answer: {result['answer']}")
    print(f"Status: {result['status']}")
    print(f"Total Duration: {result['total_duration_ms']:.2f}ms")
    print(f"Steps: {len(result['steps'])}")
    
    for step in result['steps']:
        print(f"  - Step {step['step_number']}: {step['thought']}")
        
    assert result['answer'] == "42"
    assert len(result['steps']) == 2
    assert result['status'] == ReasoningStatus.COMPLETED
    
    print("\nVerification successful!")

if __name__ == "__main__":
    asyncio.run(main())
