"""
Prometheus metrics for LLM evaluation (RAGAS-style scores).
"""

try:
    from prometheus_client import Counter, Histogram, Gauge
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False

    class _Noop:
        """No-op stub for prometheus metrics when prometheus_client is not installed."""
        def __init__(self, *args, **kwargs):
            # Intentionally empty: this is a stub when prometheus_client is unavailable.
            pass

        def labels(self, *args, **kwargs):
            return self

        def inc(self, *args, **kwargs):
            # Intentionally empty: no metrics backend is installed.
            pass

        def dec(self, *args, **kwargs):
            # Intentionally empty: no metrics backend is installed.
            pass

        def set(self, *args, **kwargs):
            # Intentionally empty: no metrics backend is installed.
            pass

        def observe(self, *args, **kwargs):
            # Intentionally empty: no metrics backend is installed.
            pass

        def time(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            # Intentionally empty: no timer context cleanup is required.
            pass

    Counter = Histogram = Gauge = _Noop


EVAL_LABELS = ["model", "prompt_type", "retriever", "dataset", "env", "version"]

llm_eval_faithfulness_score = Gauge(
    "llm_eval_faithfulness_score",
    "Faithfulness score from RAGAS evaluation",
    EVAL_LABELS,
)

llm_eval_context_precision_score = Gauge(
    "llm_eval_context_precision_score",
    "Context precision score from RAGAS evaluation",
    EVAL_LABELS,
)

llm_eval_response_relevancy_score = Gauge(
    "llm_eval_response_relevancy_score",
    "Response relevancy score from RAGAS evaluation",
    EVAL_LABELS,
)

llm_eval_noise_sensitivity_score = Gauge(
    "llm_eval_noise_sensitivity_score",
    "Noise sensitivity score from RAGAS evaluation",
    EVAL_LABELS,
)

llm_eval_runs_total = Counter(
    "llm_eval_runs_total",
    "Total number of LLM evaluation runs",
    ["model", "env", "status"],
)
