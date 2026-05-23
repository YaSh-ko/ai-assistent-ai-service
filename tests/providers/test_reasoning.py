"""
Tests for reasoning engine providers and factory.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.factory.reasoning_factory import ReasoningFactory
from app.providers.reasoning.cot_provider import CoTProvider
from app.providers.reasoning.reflection_provider import ReflectionProvider
from app.reasoning.types import ReasoningStatus


def test_reasoning_factory_cot():
    """Test that factory can create CoT engine."""
    engine = ReasoningFactory.get_reasoning_engine("cot")
    assert engine is not None
    assert isinstance(engine, CoTProvider)


def test_reasoning_factory_reflection():
    """Test that factory can create Reflection engine."""
    engine = ReasoningFactory.get_reasoning_engine("reflection")
    assert engine is not None
    assert isinstance(engine, ReflectionProvider)


def test_reasoning_factory_invalid_engine():
    """Test that factory raises error for invalid engine type."""
    with pytest.raises(ValueError, match="Unknown reasoning engine type"):
        ReasoningFactory.get_reasoning_engine("nonexistent")


def test_reasoning_factory_singleton():
    """Test that factory returns same instance for same engine type."""
    engine1 = ReasoningFactory.get_reasoning_engine("cot")
    engine2 = ReasoningFactory.get_reasoning_engine("cot")
    assert engine1 is engine2


@pytest.mark.asyncio
async def test_cot_provider_interface():
    """Test that CoT provider implements the reasoning interface correctly."""
    mock_model = AsyncMock()
    mock_model.generate.return_value = MagicMock(content="Test response")
    mock_model.model_name = "test_model"
    
    with patch("app.factory.model_factory.ModelFactory.get_model", return_value=mock_model):
        engine = ReasoningFactory.get_reasoning_engine("cot")
        
        # Test that it has required methods
        assert hasattr(engine, "reason")
        assert hasattr(engine, "get_reasoning_steps")
        assert hasattr(engine, "get_metadata")
        
        # Test metadata
        metadata = engine.get_metadata()
        assert "engine_type" in metadata or "type" in metadata


@pytest.mark.asyncio
async def test_reflection_provider_interface():
    """Test that Reflection provider implements the reasoning interface correctly."""
    mock_model = AsyncMock()
    mock_model.generate.return_value = MagicMock(content="0.85")
    mock_model.model_name = "test_model"
    
    with patch("app.factory.model_factory.ModelFactory.get_model", return_value=mock_model):
        engine = ReasoningFactory.get_reasoning_engine("reflection")
        
        # Test that it has required methods
        assert hasattr(engine, "reason")
        assert hasattr(engine, "get_reasoning_steps")
        assert hasattr(engine, "get_metadata")
        
        # Test metadata
        metadata = engine.get_metadata()
        assert "engine_type" in metadata or "type" in metadata


def test_reasoning_factory_clear_cache():
    """Test that we can clear the factory cache."""
    # Get an engine to populate cache
    engine1 = ReasoningFactory.get_reasoning_engine("cot")
    
    # Clear cache
    ReasoningFactory._instances.clear()
    
    # Get engine again - should be a new instance
    engine2 = ReasoningFactory.get_reasoning_engine("cot")
    
    # They should be different instances now
    assert engine1 is not engine2

