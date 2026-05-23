"""
Tests for ReasoningService.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.reasoning_service import ReasoningService
from app.reasoning.types import ReasoningStatus


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock REASONING_CONFIG settings."""
    mock_conf = {
        "default_engine": "cot",
        "cot": {
            "max_reasoning_depth": 3,
            "max_clarifying_questions": 2,
            "enable_verification": True,
            "neo4j_max_depth": 2,
            "timeout_per_step": 5
        },
        "reflection": {
            "max_iterations": 3,
            "quality_threshold": 0.8,
            "critique_temperature": 0.3,
            "refinement_temperature": 0.7
        },
        "task_mapping": {
            "complex": "cot",
            "simple_question": "cot",
            "analysis": "reflection"
        }
    }
    # Use monkeypatch to set the config
    from app.core import config
    monkeypatch.setattr(config.settings, "REASONING_CONFIG", mock_conf)
    return mock_conf


@pytest.fixture
def mock_engine():
    """Create a mock reasoning engine."""
    engine = AsyncMock()
    engine.reason.return_value = {
        "answer": "Test answer",
        "status": ReasoningStatus.COMPLETED,
        "steps": [],
        "total_duration_ms": 100.0,
        "total_tokens": 50,
        "metadata": {"type": "cot"},
        "error": None
    }
    engine.__class__.__name__ = "MockEngine"
    return engine


@pytest.mark.asyncio
async def test_reasoning_service_execution(mock_settings, mock_engine):
    """Test that ReasoningService executes reasoning correctly."""
    
    with patch("app.factory.reasoning_factory.ReasoningFactory.get_reasoning_engine", return_value=mock_engine):
        service = ReasoningService()
        
        result = await service.execute_reasoning(
            question="Test question",
            task_type="complex",
            user_id="user1"
        )
        
        # Verify result structure
        assert result["answer"] == "Test answer"
        assert result["status"] == ReasoningStatus.COMPLETED
        assert "reasoning_id" in result
        
        # Verify engine was called
        mock_engine.reason.assert_called_once()


@pytest.mark.asyncio
async def test_reasoning_service_with_context(mock_settings, mock_engine):
    """Test reasoning with context."""
    
    with patch("app.factory.reasoning_factory.ReasoningFactory.get_reasoning_engine", return_value=mock_engine):
        service = ReasoningService()
        
        context = {"search_results": ["result1", "result2"]}
        
        result = await service.execute_reasoning(
            question="Test question",
            context=context,
            task_type="complex",
            user_id="user1"
        )
        
        # Verify context was passed
        call_args = mock_engine.reason.call_args
        assert call_args[1]["context"] == context


@pytest.mark.asyncio
async def test_reasoning_service_error_handling(mock_settings, mock_engine):
    """Test error handling in reasoning service."""
    
    # Make engine raise an error
    mock_engine.reason.side_effect = Exception("Test error")
    
    with patch("app.factory.reasoning_factory.ReasoningFactory.get_reasoning_engine", return_value=mock_engine):
        service = ReasoningService()
        
        result = await service.execute_reasoning(
            question="Test question",
            task_type="complex",
            user_id="user1"
        )
        
        # Verify error handling
        assert result["status"] == "failed"
        assert "error" in result
        assert "Test error" in result["error"]


@pytest.mark.asyncio
async def test_reasoning_service_engine_selection(mock_settings, mock_engine):
    """Test that ReasoningService selects the correct engine based on task type."""
    
    with patch("app.factory.reasoning_factory.ReasoningFactory.get_reasoning_engine", return_value=mock_engine) as mock_factory:
        service = ReasoningService()
        
        # Test complex task
        await service.execute_reasoning(
            question="Complex question",
            task_type="complex",
            user_id="user1"
        )
        
        # Verify correct engine was requested
        mock_factory.assert_called_with("cot")


def test_reasoning_service_get_reasoning_info(mock_settings):
    """Test retrieving reasoning history."""
    
    service = ReasoningService()
    
    # Manually add a reasoning result
    reasoning_id = "test_reasoning_123"
    test_result = {
        "answer": "Test answer",
        "status": "completed"
    }
    service._save_reasoning_info(reasoning_id, test_result, "CoTReasoning")
    
    # Retrieve it
    info = service.get_reasoning_info(reasoning_id)
    
    assert info is not None
    assert info["id"] == reasoning_id
    assert info["engine"] == "CoTReasoning"
    assert info["result"] == test_result


def test_reasoning_service_warmup(mock_settings, mock_engine):
    """Test warmup functionality."""
    
    with patch("app.factory.reasoning_factory.ReasoningFactory.get_reasoning_engine", return_value=mock_engine) as mock_factory:
        service = ReasoningService()
        service.warmup()
        
        # Verify engines were initialized
        assert mock_factory.call_count >= 1  # At least default engine


@pytest.mark.asyncio
async def test_reasoning_service_fallback_to_default(mock_settings, mock_engine):
    """Test fallback to default engine when requested engine fails."""
    
    def side_effect(engine_name):
        if engine_name == "nonexistent":
            raise ValueError("Unknown engine")
        return mock_engine
    
    with patch("app.factory.reasoning_factory.ReasoningFactory.get_reasoning_engine", side_effect=side_effect):
        with patch("app.utils.helpers.select_reasoning_engine", return_value="nonexistent"):
            service = ReasoningService()
            
            result = await service.execute_reasoning(
                question="Test question",
                task_type="unknown_task",
                user_id="user1"
            )
            
            # Should still get a result from fallback
            assert result["answer"] == "Test answer"
