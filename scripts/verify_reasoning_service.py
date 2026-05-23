import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

# Mock dependencies
sys.modules["pydantic"] = MagicMock()
sys.modules["pydantic_settings"] = MagicMock()

mock_settings = MagicMock()
mock_settings.REASONING_CONFIG = {
    "default_engine": "cot",
    "task_mapping": {"complex": "cot"}
}
sys.modules["app.core.config"] = MagicMock()
sys.modules["app.core.config"].settings = mock_settings

# Mock Factory
mock_engine = AsyncMock()
mock_engine.reason.return_value = {"answer": "42", "status": "completed"}
mock_factory = MagicMock()
mock_factory.get_reasoning_engine.return_value = mock_engine
sys.modules["app.factory.reasoning_factory"] = MagicMock()
sys.modules["app.factory.reasoning_factory"].ReasoningFactory = mock_factory

# Mock Helpers
sys.modules["app.utils.helpers"] = MagicMock()
sys.modules["app.utils.helpers"].select_reasoning_engine.return_value = "cot"

from app.services.reasoning_service import ReasoningService

async def main():
    print("Testing ReasoningService...")
    
    service = ReasoningService()
    
    # Test warmup
    service.warmup()
    print("Warmup completed")
    
    # Test execution
    result = await service.execute_reasoning(
        question="What is 6*7?",
        task_type="complex",
        user_id="test_user"
    )
    
    print(f"Result: {result}")
    assert result['answer'] == "42"
    assert "reasoning_id" in result
    
    # Test history retrieval
    info = service.get_reasoning_info(result['reasoning_id'])
    assert info is not None
    assert info['result']['answer'] == "42"
    print("History retrieval verified")
    
    print("\nVerification successful!")

if __name__ == "__main__":
    asyncio.run(main())
