import sys
import os
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

# Mock pydantic and config
sys.modules["pydantic"] = MagicMock()
sys.modules["pydantic_settings"] = MagicMock()

mock_settings = MagicMock()
mock_settings.CURRENT_MODEL = "gigachat"
mock_settings.COT_CONFIG = {"max_reasoning_depth": 4}
mock_settings.REASONING_CONFIG = {
    "default_engine": "cot",
    "cot": mock_settings.COT_CONFIG,
    "task_mapping": {"complex": "cot"}
}

sys.modules["app.core.config"] = MagicMock()
sys.modules["app.core.config"].settings = mock_settings

# Mock ModelFactory
mock_model_factory = MagicMock()
mock_model_provider = MagicMock()
mock_model_factory.get_model.return_value = mock_model_provider
sys.modules["app.factory.model_factory"] = MagicMock()
sys.modules["app.factory.model_factory"].ModelFactory = mock_model_factory

from app.factory.reasoning_factory import ReasoningFactory
from app.utils.helpers import select_reasoning_engine
from app.providers.reasoning.cot_provider import CoTProvider

def main():
    print("Testing ReasoningFactory...")
    
    # Test creation
    engine = ReasoningFactory.get_reasoning_engine("cot")
    assert isinstance(engine, CoTProvider)
    print("Successfully created CoTProvider")
    
    # Test singleton
    engine2 = ReasoningFactory.get_reasoning_engine("cot")
    assert engine is engine2
    print("Singleton behavior verified")
    
    # Test helper
    engine_type = select_reasoning_engine("complex")
    assert engine_type == "cot"
    print(f"Helper selected: {engine_type}")
    
    fallback = select_reasoning_engine("unknown_task")
    assert fallback == "cot"
    print(f"Helper fallback: {fallback}")
    
    print("\nVerification successful!")

if __name__ == "__main__":
    main()
