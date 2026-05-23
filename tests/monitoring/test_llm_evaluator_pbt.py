"""
Property-based tests for app.monitoring.llm_evaluator.

Uses Hypothesis. Does NOT require ragas or prometheus_client to be installed.

Feature: llm-metrics-grafana
"""

import asyncio
import sys
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Mock ragas and datasets before any app imports
# ---------------------------------------------------------------------------
for _mod in ("ragas", "datasets"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# ---------------------------------------------------------------------------
# Lazy imports (after mocks are in place)
# ---------------------------------------------------------------------------
from app.monitoring.llm_evaluator import (  # noqa: E402
    RAGTrace,
    REQUIRED_FIELDS,
    clamp_score,
    LLMEvaluator,
)
import app.monitoring.eval_metrics as em  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def valid_trace_dict() -> dict:
    return {
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


def rag_trace_strategy():
    """Hypothesis strategy that generates valid RAGTrace instances."""
    return st.builds(
        RAGTrace,
        question=st.text(min_size=1, max_size=200),
        context=st.lists(st.text(min_size=1, max_size=100), min_size=1, max_size=5),
        answer=st.text(min_size=1, max_size=200),
        model=st.text(min_size=1, max_size=50),
        prompt_type=st.text(min_size=1, max_size=50),
        retriever=st.text(min_size=1, max_size=50),
        dataset=st.text(min_size=1, max_size=50),
        env=st.text(min_size=1, max_size=50),
        version=st.text(min_size=1, max_size=50),
    )


# ===========================================================================
# Property 3 — Score clamping invariant
# Validates: Requirements 2.6
# ===========================================================================

# Feature: llm-metrics-grafana, Property 3: score clamping invariant
@given(st.floats(allow_nan=True, allow_infinity=True))
@settings(max_examples=100)
def test_score_clamping(raw_score):
    """**Validates: Requirements 2.6**

    For any float (including NaN, ±inf, out-of-range values), clamp_score
    must always return a value in [0.0, 1.0].
    """
    result = clamp_score(raw_score)
    assert 0.0 <= result <= 1.0


# ===========================================================================
# Property 4 — RAGTrace serialization round-trip
# Validates: Requirements 7.1, 7.2, 7.3
# ===========================================================================

# Feature: llm-metrics-grafana, Property 4: RAGTrace serialization round-trip
@given(rag_trace_strategy())
@settings(max_examples=100)
def test_ragtrace_roundtrip(trace):
    """**Validates: Requirements 7.1, 7.2, 7.3**

    For any valid RAGTrace, serializing to dict and deserializing back must
    produce an object equal to the original.
    """
    assert RAGTrace.from_dict(trace.to_dict()) == trace


# ===========================================================================
# Property 5 — Missing required field raises ValueError
# Validates: Requirements 7.4
# ===========================================================================

# Feature: llm-metrics-grafana, Property 5: missing field raises ValueError
@given(st.sampled_from(REQUIRED_FIELDS))
@settings(max_examples=100)
def test_missing_field_raises(field_name):
    """**Validates: Requirements 7.4**

    For any required field, deserializing a dict with that field absent must
    raise a ValueError whose message identifies the missing field.
    """
    d = valid_trace_dict()
    del d[field_name]
    with pytest.raises(ValueError, match=field_name):
        RAGTrace.from_dict(d)


# ===========================================================================
# Property 6 — Counter incremented exactly once per eval run
# Validates: Requirements 3.5, 3.7, 2.5
# ===========================================================================

# Feature: llm-metrics-grafana, Property 6: counter incremented on every eval run
@given(rag_trace_strategy(), st.booleans())
@settings(max_examples=100)
def test_counter_always_incremented(trace, ragas_raises):
    """**Validates: Requirements 3.5, 3.7, 2.5**

    Regardless of whether RAGAS succeeds or raises, llm_eval_runs_total must
    be incremented exactly once per _run_eval call.
    """
    asyncio.run(_test_counter_always_incremented_impl(trace, ragas_raises))


async def _test_counter_always_incremented_impl(trace: RAGTrace, ragas_raises: bool):
    evaluator = LLMEvaluator()
    inc_calls = []

    mock_counter = MagicMock()
    mock_gauge = MagicMock()

    # Track every call to .inc() via the labels() chain
    def make_labels_mock(**kwargs):
        labels_mock = MagicMock()
        labels_mock.inc.side_effect = lambda: inc_calls.append(kwargs)
        return labels_mock

    mock_counter.labels.side_effect = make_labels_mock

    async def mock_call_ragas(_trace):
        if ragas_raises:
            raise RuntimeError("RAGAS failed")
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
        await evaluator._run_eval(trace)

    # Counter must be incremented exactly once
    assert len(inc_calls) == 1, (
        f"Expected counter.inc() called exactly once, got {len(inc_calls)} calls"
    )


# ===========================================================================
# Property 7 — Timeout always results in status="error" counter increment
# Validates: Requirements 6.5, 6.6
# ===========================================================================

# Feature: llm-metrics-grafana, Property 7: timeout cancels eval run
@given(st.integers(min_value=1, max_value=5))
@settings(max_examples=100)
def test_timeout_increments_error_counter(timeout_seconds):
    """**Validates: Requirements 6.5, 6.6**

    When RAGAS takes longer than the configured timeout, _run_eval must
    cancel the run and increment llm_eval_runs_total with status="error".
    """
    asyncio.run(_test_timeout_increments_error_counter_impl(timeout_seconds))


async def _test_timeout_increments_error_counter_impl(timeout_seconds: int):
    evaluator = LLMEvaluator()
    error_inc_calls = []

    mock_counter = MagicMock()
    mock_gauge = MagicMock()

    def make_labels_mock(**kwargs):
        labels_mock = MagicMock()
        if kwargs.get("status") == "error":
            labels_mock.inc.side_effect = lambda: error_inc_calls.append(kwargs)
        return labels_mock

    mock_counter.labels.side_effect = make_labels_mock

    async def slow_ragas(_trace):
        # Sleep much longer than any timeout used in the test
        await asyncio.sleep(9999)

    trace = RAGTrace(
        question="q",
        context=["ctx"],
        answer="a",
        model="m",
        prompt_type="p",
        retriever="r",
        dataset="d",
        env="e",
        version="v",
    )

    with patch("app.monitoring.llm_evaluator._RAGAS_AVAILABLE", True), \
         patch.object(evaluator, "_call_ragas", slow_ragas), \
         patch.object(em, "llm_eval_runs_total", mock_counter), \
         patch.object(em, "llm_eval_faithfulness_score", mock_gauge), \
         patch.object(em, "llm_eval_context_precision_score", mock_gauge), \
         patch.object(em, "llm_eval_response_relevancy_score", mock_gauge), \
         patch.object(em, "llm_eval_noise_sensitivity_score", mock_gauge), \
         patch("app.core.config.settings.LLM_EVAL_TIMEOUT_SECONDS", 0.001):
        await evaluator._run_eval(trace)

    assert len(error_inc_calls) == 1, (
        f"Expected status='error' counter increment exactly once on timeout, "
        f"got {len(error_inc_calls)}"
    )
