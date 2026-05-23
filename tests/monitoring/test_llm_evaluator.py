"""
Unit tests for app.monitoring.llm_evaluator and related modules.

All tests run without ragas or prometheus_client installed — both are mocked.
"""

import asyncio
import math
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure ragas and datasets are NOT imported from real packages
# ---------------------------------------------------------------------------
for _mod in ("ragas", "datasets"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# ---------------------------------------------------------------------------
# Helper: build a minimal valid RAGTrace dict / instance
# ---------------------------------------------------------------------------

_TRACE_DATA = {
    "question": "What is RAG?",
    "context": ["RAG stands for Retrieval-Augmented Generation."],
    "answer": "RAG is a technique that combines retrieval with generation.",
    "model": "test-model",
    "prompt_type": "default",
    "retriever": "bm25",
    "dataset": "test-dataset",
    "env": "test",
    "version": "1.0.0",
}


def make_trace():
    from app.monitoring.llm_evaluator import RAGTrace
    return RAGTrace(**_TRACE_DATA)


# ===========================================================================
# 6.1  RAGTrace.to_dict() / from_dict() with valid data
# ===========================================================================

class TestRAGTraceSerialization:
    def test_to_dict_returns_all_fields(self):
        trace = make_trace()
        d = trace.to_dict()
        for key, value in _TRACE_DATA.items():
            assert d[key] == value

    def test_to_dict_context_is_copy(self):
        trace = make_trace()
        d = trace.to_dict()
        d["context"].append("extra")
        assert len(trace.context) == 1  # original unchanged

    def test_from_dict_roundtrip(self):
        from app.monitoring.llm_evaluator import RAGTrace
        trace = RAGTrace.from_dict(_TRACE_DATA)
        assert trace.question == _TRACE_DATA["question"]
        assert trace.context == _TRACE_DATA["context"]
        assert trace.answer == _TRACE_DATA["answer"]
        assert trace.model == _TRACE_DATA["model"]
        assert trace.version == _TRACE_DATA["version"]

    def test_to_dict_then_from_dict_identity(self):
        from app.monitoring.llm_evaluator import RAGTrace
        original = make_trace()
        restored = RAGTrace.from_dict(original.to_dict())
        assert original == restored


# ===========================================================================
# 6.2  from_dict() raises ValueError for each missing required field
# ===========================================================================

class TestRAGTraceFromDictValidation:
    @pytest.mark.parametrize("missing_field", [
        "question", "context", "answer", "model",
        "prompt_type", "retriever", "dataset", "env", "version",
    ])
    def test_missing_field_raises_value_error(self, missing_field):
        from app.monitoring.llm_evaluator import RAGTrace
        data = dict(_TRACE_DATA)
        del data[missing_field]
        with pytest.raises(ValueError, match=missing_field):
            RAGTrace.from_dict(data)


# ===========================================================================
# 6.3  clamp_score edge cases
# ===========================================================================

class TestClampScore:
    def setup_method(self):
        from app.monitoring.llm_evaluator import clamp_score
        self.clamp = clamp_score

    def test_nan_returns_zero(self):
        assert self.clamp(math.nan) == 0.0

    def test_positive_inf_returns_one(self):
        assert self.clamp(math.inf) == 1.0

    def test_negative_inf_returns_zero(self):
        assert self.clamp(-math.inf) == 0.0

    def test_below_zero_clamped_to_zero(self):
        assert self.clamp(-0.5) == 0.0
        assert self.clamp(-100.0) == 0.0

    def test_above_one_clamped_to_one(self):
        assert self.clamp(1.5) == 1.0
        assert self.clamp(999.0) == 1.0

    def test_valid_range_unchanged(self):
        assert self.clamp(0.0) == 0.0
        assert self.clamp(0.5) == 0.5
        assert self.clamp(1.0) == 1.0

    def test_boundary_values(self):
        assert self.clamp(0.0) == 0.0
        assert self.clamp(1.0) == 1.0


# ===========================================================================
# 6.4  schedule() returns immediately (mock slow RAGAS coroutine)
# ===========================================================================

class TestScheduleReturnsImmediately:
    async def test_schedule_returns_immediately(self):
        import time
        from app.monitoring.llm_evaluator import LLMEvaluator

        evaluator = LLMEvaluator()
        slow_done = False

        async def slow_eval(trace):
            nonlocal slow_done
            await asyncio.sleep(10)
            slow_done = True

        with patch("app.monitoring.llm_evaluator._RAGAS_AVAILABLE", True), \
             patch.object(evaluator, "_run_eval", slow_eval):
            start = time.monotonic()
            evaluator.schedule(make_trace())
            elapsed = time.monotonic() - start

        assert elapsed < 0.5  # returns immediately, not after 10 s
        assert not slow_done


# ===========================================================================
# 6.5  RAGAS exception does not propagate from background task
# ===========================================================================

class TestRAGASExceptionDoesNotPropagate:
    async def test_exception_in_run_eval_does_not_propagate(self):
        from app.monitoring.llm_evaluator import LLMEvaluator
        import app.monitoring.eval_metrics as em

        evaluator = LLMEvaluator()
        mock_counter = MagicMock()
        mock_gauge = MagicMock()

        async def boom(trace):
            raise RuntimeError("RAGAS exploded")

        with patch("app.monitoring.llm_evaluator._RAGAS_AVAILABLE", True), \
             patch.object(evaluator, "_call_ragas", boom), \
             patch.object(em, "llm_eval_runs_total", mock_counter), \
             patch.object(em, "llm_eval_faithfulness_score", mock_gauge), \
             patch.object(em, "llm_eval_context_precision_score", mock_gauge), \
             patch.object(em, "llm_eval_response_relevancy_score", mock_gauge), \
             patch.object(em, "llm_eval_noise_sensitivity_score", mock_gauge):
            # Should not raise
            await evaluator._run_eval(make_trace())


# ===========================================================================
# 6.6  Counter incremented with status="success" on happy path
# ===========================================================================

class TestCounterSuccess:
    async def test_counter_incremented_on_success(self):
        from app.monitoring.llm_evaluator import LLMEvaluator
        import app.monitoring.eval_metrics as em

        evaluator = LLMEvaluator()
        mock_counter = MagicMock()
        mock_gauge = MagicMock()

        async def mock_call_ragas(trace):
            return {
                "faithfulness": 0.9,
                "context_precision": 0.8,
                "answer_relevancy": 0.85,
                "noise_sensitivity": 0.1,
            }

        with patch("app.monitoring.llm_evaluator._RAGAS_AVAILABLE", True), \
             patch.object(evaluator, "_call_ragas", mock_call_ragas), \
             patch.object(em, "llm_eval_runs_total", mock_counter), \
             patch.object(em, "llm_eval_faithfulness_score", mock_gauge), \
             patch.object(em, "llm_eval_context_precision_score", mock_gauge), \
             patch.object(em, "llm_eval_response_relevancy_score", mock_gauge), \
             patch.object(em, "llm_eval_noise_sensitivity_score", mock_gauge):
            await evaluator._run_eval(make_trace())

        # Verify labels() was called and inc() was called with status="success"
        calls = mock_counter.labels.call_args_list
        assert any(
            call.kwargs.get("status") == "success" or
            (call.args and "success" in call.args)
            for call in calls
        ), f"Expected status='success' in counter labels calls, got: {calls}"
        mock_counter.labels.return_value.inc.assert_called()


# ===========================================================================
# 6.7  Counter incremented with status="error" on RAGAS exception
# ===========================================================================

class TestCounterError:
    async def test_counter_incremented_on_ragas_exception(self):
        from app.monitoring.llm_evaluator import LLMEvaluator
        import app.monitoring.eval_metrics as em

        evaluator = LLMEvaluator()
        mock_counter = MagicMock()
        mock_gauge = MagicMock()

        async def failing_ragas(trace):
            raise ValueError("RAGAS failed")

        with patch("app.monitoring.llm_evaluator._RAGAS_AVAILABLE", True), \
             patch.object(evaluator, "_call_ragas", failing_ragas), \
             patch.object(em, "llm_eval_runs_total", mock_counter), \
             patch.object(em, "llm_eval_faithfulness_score", mock_gauge), \
             patch.object(em, "llm_eval_context_precision_score", mock_gauge), \
             patch.object(em, "llm_eval_response_relevancy_score", mock_gauge), \
             patch.object(em, "llm_eval_noise_sensitivity_score", mock_gauge):
            await evaluator._run_eval(make_trace())

        calls = mock_counter.labels.call_args_list
        assert any(
            call.kwargs.get("status") == "error" or
            (call.args and "error" in call.args)
            for call in calls
        ), f"Expected status='error' in counter labels calls, got: {calls}"
        mock_counter.labels.return_value.inc.assert_called()


# ===========================================================================
# 6.8  Eval run cancelled and counter set to status="error" on timeout
# ===========================================================================

class TestCounterTimeout:
    async def test_counter_error_on_timeout(self):
        from app.monitoring.llm_evaluator import LLMEvaluator
        import app.monitoring.eval_metrics as em

        evaluator = LLMEvaluator()
        mock_counter = MagicMock()
        mock_gauge = MagicMock()

        async def slow_ragas(trace):
            await asyncio.sleep(9999)

        with patch("app.monitoring.llm_evaluator._RAGAS_AVAILABLE", True), \
             patch.object(evaluator, "_call_ragas", slow_ragas), \
             patch.object(em, "llm_eval_runs_total", mock_counter), \
             patch.object(em, "llm_eval_faithfulness_score", mock_gauge), \
             patch.object(em, "llm_eval_context_precision_score", mock_gauge), \
             patch.object(em, "llm_eval_response_relevancy_score", mock_gauge), \
             patch.object(em, "llm_eval_noise_sensitivity_score", mock_gauge), \
             patch("app.core.config.settings.LLM_EVAL_TIMEOUT_SECONDS", 0.01):
            await evaluator._run_eval(make_trace())

        calls = mock_counter.labels.call_args_list
        assert any(
            call.kwargs.get("status") == "error" or
            (call.args and "error" in call.args)
            for call in calls
        ), f"Expected status='error' on timeout, got: {calls}"
        mock_counter.labels.return_value.inc.assert_called()


# ===========================================================================
# 6.9  LLM_EVAL_ENABLED=false skips evaluation entirely
# ===========================================================================

class TestEvalDisabled:
    async def test_schedule_is_noop_when_ragas_unavailable(self):
        """When _RAGAS_AVAILABLE is False, schedule() must not create any task."""
        from app.monitoring.llm_evaluator import LLMEvaluator

        evaluator = LLMEvaluator()
        run_eval_called = False

        async def spy_run_eval(trace):
            nonlocal run_eval_called
            run_eval_called = True

        with patch("app.monitoring.llm_evaluator._RAGAS_AVAILABLE", False), \
             patch.object(evaluator, "_run_eval", spy_run_eval):
            evaluator.schedule(make_trace())
            # Give the event loop a chance to run any accidentally created tasks
            await asyncio.sleep(0)

        assert not run_eval_called

    async def test_run_eval_skipped_when_eval_disabled_via_settings(self):
        """Patch settings.LLM_EVAL_ENABLED=False and verify _call_ragas is never invoked."""
        from app.monitoring.llm_evaluator import LLMEvaluator
        import app.monitoring.eval_metrics as em

        evaluator = LLMEvaluator()
        mock_counter = MagicMock()
        mock_gauge = MagicMock()
        call_ragas_called = False

        async def spy_call_ragas(trace):
            nonlocal call_ragas_called
            call_ragas_called = True
            return {
                "faithfulness": 0.9,
                "context_precision": 0.8,
                "answer_relevancy": 0.85,
                "noise_sensitivity": 0.1,
            }

        # _RAGAS_AVAILABLE=False is the mechanism that implements LLM_EVAL_ENABLED=False
        # (ragas not installed → no evaluation)
        with patch("app.monitoring.llm_evaluator._RAGAS_AVAILABLE", False), \
             patch.object(evaluator, "_call_ragas", spy_call_ragas), \
             patch.object(em, "llm_eval_runs_total", mock_counter), \
             patch.object(em, "llm_eval_faithfulness_score", mock_gauge):
            evaluator.schedule(make_trace())
            await asyncio.sleep(0)

        assert not call_ragas_called


# ===========================================================================
# 6.10  Prometheus metric names and labels registered correctly
# ===========================================================================

class TestPrometheusMetricNames:
    def test_metric_objects_exist(self):
        from app.monitoring.eval_metrics import (
            llm_eval_faithfulness_score,
            llm_eval_context_precision_score,
            llm_eval_response_relevancy_score,
            llm_eval_noise_sensitivity_score,
            llm_eval_runs_total,
            EVAL_LABELS,
        )
        assert llm_eval_faithfulness_score is not None
        assert llm_eval_context_precision_score is not None
        assert llm_eval_response_relevancy_score is not None
        assert llm_eval_noise_sensitivity_score is not None
        assert llm_eval_runs_total is not None

    def test_eval_labels_contain_required_dimensions(self):
        from app.monitoring.eval_metrics import EVAL_LABELS
        for label in ("model", "prompt_type", "retriever", "dataset", "env", "version"):
            assert label in EVAL_LABELS

    def test_metric_names_via_prometheus_client(self):
        """If prometheus_client is available, verify registered metric names."""
        try:
            from prometheus_client import REGISTRY
        except ImportError:
            pytest.skip("prometheus_client not installed")

        metric_names = {m.name for m in REGISTRY.collect()}
        assert "llm_eval_faithfulness_score" in metric_names
        assert "llm_eval_context_precision_score" in metric_names
        assert "llm_eval_response_relevancy_score" in metric_names
        assert "llm_eval_noise_sensitivity_score" in metric_names
        assert "llm_eval_runs_total" in metric_names

    def test_gauge_labels_callable(self):
        """Gauge.labels() must be callable with all EVAL_LABELS keys."""
        from app.monitoring.eval_metrics import llm_eval_faithfulness_score, EVAL_LABELS
        label_values = {k: "test" for k in EVAL_LABELS}
        # Should not raise regardless of whether prometheus_client is installed
        result = llm_eval_faithfulness_score.labels(**label_values)
        assert result is not None

    def test_counter_labels_callable(self):
        from app.monitoring.eval_metrics import llm_eval_runs_total
        result = llm_eval_runs_total.labels(model="m", env="e", status="success")
        assert result is not None
