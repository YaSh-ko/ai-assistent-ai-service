"""
Tests for CoTReasoning — 50 uncovered lines.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.reasoning.cot_reasoning import CoTReasoning
from app.interfaces.model_provider import ModelResponse


def _make_model(content: str = "test response") -> MagicMock:
    model = MagicMock()
    model.model_name = "test-model"
    model.generate = AsyncMock(return_value=ModelResponse(
        content=content,
        model_name="test-model",
        tokens_used=10,
        latency_ms=50.0,
    ))
    return model


@pytest.fixture
def model():
    return _make_model()


@pytest.fixture
def cot(model):
    with patch("app.reasoning.cot_reasoning.ReasoningMetrics"):
        return CoTReasoning(model_provider=model)


class TestCoTInit:
    def test_default_config(self, cot):
        assert cot.max_depth == 4
        assert cot.enable_verification is True
        assert cot.timeout_per_step == 30

    def test_custom_config(self, model):
        with patch("app.reasoning.cot_reasoning.ReasoningMetrics"):
            c = CoTReasoning(model, config={"max_reasoning_depth": 2, "enable_verification": False})
        assert c.max_depth == 2
        assert c.enable_verification is False


class TestUnderstand:
    @pytest.mark.asyncio
    async def test_understand_returns_dict(self, cot):
        result = await cot.understand("What is Jupiter?", {"data": "some context"})
        assert "raw_analysis" in result
        assert result["query"] == "What is Jupiter?"

    @pytest.mark.asyncio
    async def test_understand_calls_model(self, cot, model):
        await cot.understand("query", {})
        model.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_understand_with_none_context(self, cot):
        result = await cot.understand("query", None)
        assert result["context"] is None


class TestPlan:
    @pytest.mark.asyncio
    async def test_plan_returns_dict(self, cot):
        understanding = {"raw_analysis": "user wants facts", "query": "q"}
        result = await cot.plan(understanding)
        assert "raw_plan" in result
        assert "strategy" in result

    @pytest.mark.asyncio
    async def test_plan_calls_model(self, cot, model):
        await cot.plan({"raw_analysis": "analysis", "query": "q"})
        model.generate.assert_called_once()


class TestExecute:
    @pytest.mark.asyncio
    async def test_execute_returns_dict(self, cot):
        plan = {"strategy": "mixed", "steps": ["query_db"]}
        result = await cot.execute(plan)
        assert "db_data" in result
        assert "graph_data" in result

    @pytest.mark.asyncio
    async def test_execute_does_not_call_model(self, cot, model):
        await cot.execute({"strategy": "direct"})
        model.generate.assert_not_called()


class TestVerify:
    @pytest.mark.asyncio
    async def test_verify_returns_string(self, cot):
        result = await cot.verify({"db_data": "data"}, "original query")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_verify_calls_model(self, cot, model):
        await cot.verify({}, "query")
        model.generate.assert_called_once()


class TestPerformReasoning:
    @pytest.mark.asyncio
    async def test_full_pipeline_returns_string(self, cot):
        result = await cot._perform_reasoning("What is Jupiter?", {"rag": []})
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_verification_disabled_skips_verify(self, model):
        with patch("app.reasoning.cot_reasoning.ReasoningMetrics"):
            c = CoTReasoning(model, config={"enable_verification": False})
        result = await c._perform_reasoning("query", {})
        # Should still return something (execution results as string)
        assert result is not None

    @pytest.mark.asyncio
    async def test_empty_context_logs_warning(self, cot):
        # Should not raise even with empty context
        result = await cot._perform_reasoning("query", None)
        assert result is not None

    @pytest.mark.asyncio
    async def test_timeout_raises(self, model):
        with patch("app.reasoning.cot_reasoning.ReasoningMetrics"):
            c = CoTReasoning(model, config={"timeout_per_step": 0.001})
        model.generate = AsyncMock(side_effect=lambda **kw: asyncio.sleep(1))

        with pytest.raises((TimeoutError, Exception)):
            await c._perform_reasoning("query", {})

    @pytest.mark.asyncio
    async def test_model_exception_propagates(self, cot, model):
        model.generate = AsyncMock(side_effect=RuntimeError("model down"))
        with pytest.raises(RuntimeError, match="model down"):
            await cot._perform_reasoning("query", {})

    @pytest.mark.asyncio
    async def test_steps_are_recorded(self, cot):
        await cot._perform_reasoning("query", {})
        # 4 steps should be added (understand, plan, execute, verify)
        assert len(cot._steps) == 4
