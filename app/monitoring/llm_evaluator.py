"""
LLM evaluation pipeline using RAGAS.

Provides RAGTrace data model and LLMEvaluator for async, non-blocking
quality scoring of RAG pipeline outputs.
"""

import asyncio
import math
from dataclasses import dataclass
from typing import Optional

from app.monitoring.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# RAGAS import guard — if ragas is not installed, evaluation is a no-op
# ---------------------------------------------------------------------------
try:
    from ragas import evaluate  # noqa: F401
    from ragas.metrics import (  # noqa: F401
        faithfulness,
        context_precision,
        answer_relevancy,
        noise_sensitivity,
    )
    from datasets import Dataset  # noqa: F401
    _RAGAS_AVAILABLE = True
except ImportError:
    _RAGAS_AVAILABLE = False


# ---------------------------------------------------------------------------
# RAGTrace — immutable value object for one completed RAG execution
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = [
    "question",
    "context",
    "answer",
    "model",
    "prompt_type",
    "retriever",
    "dataset",
    "env",
    "version",
]


@dataclass
class RAGTrace:
    """Represents one completed RAG pipeline execution to be evaluated."""

    question: str
    context: list
    answer: str
    model: str
    prompt_type: str
    retriever: str
    dataset: str
    env: str
    version: str

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "question": self.question,
            "context": list(self.context),
            "answer": self.answer,
            "model": self.model,
            "prompt_type": self.prompt_type,
            "retriever": self.retriever,
            "dataset": self.dataset,
            "env": self.env,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RAGTrace":
        """Deserialize from a dictionary.

        Raises:
            ValueError: If any required field is missing, with the field name in the message.
        """
        for field_name in REQUIRED_FIELDS:
            if field_name not in data:
                raise ValueError(f"Missing required field: {field_name}")
        return cls(
            question=data["question"],
            context=data["context"],
            answer=data["answer"],
            model=data["model"],
            prompt_type=data["prompt_type"],
            retriever=data["retriever"],
            dataset=data["dataset"],
            env=data["env"],
            version=data["version"],
        )


# ---------------------------------------------------------------------------
# clamp_score — normalises any float to [0.0, 1.0]
# ---------------------------------------------------------------------------

def clamp_score(value: float) -> float:
    """Clamp *value* to the closed interval [0.0, 1.0].

    Special cases:
    - NaN  → 0.0
    - +inf → 1.0
    - -inf → 0.0
    - values < 0 → 0.0
    - values > 1 → 1.0
    """
    if math.isnan(value):
        return 0.0
    if math.isinf(value):
        return 1.0 if value > 0 else 0.0
    return max(0.0, min(1.0, float(value)))


# ---------------------------------------------------------------------------
# LLMEvaluator
# ---------------------------------------------------------------------------

class LLMEvaluator:
    """Async, non-blocking RAGAS evaluator.

    Call ``schedule(trace)`` from any async context after a RAG chain
    completes.  The actual scoring runs in a background task and never
    blocks the caller.
    """

    def __init__(self) -> None:
        self._background_tasks: set[asyncio.Task] = set()

    def schedule(self, trace: RAGTrace) -> None:
        """Schedule evaluation of *trace* as a background asyncio task.

        Returns immediately.  If RAGAS is not installed this is a no-op.
        If there is no running event loop a WARNING is logged and the call
        is silently skipped.
        """
        if not _RAGAS_AVAILABLE:
            return

        try:
            task = asyncio.create_task(self._run_eval(trace))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
        except RuntimeError as exc:
            logger.warning("LLMEvaluator.schedule: no running event loop — %s", exc)

    async def _run_eval(self, trace: RAGTrace) -> None:
        """Run RAGAS evaluation, clamp scores, and export to Prometheus.

        Wraps the RAGAS call in ``asyncio.wait_for`` using the configured
        timeout.  Increments ``llm_eval_runs_total`` on every exit path.
        """
        from app.core.config import settings
        from app.monitoring.eval_metrics import (
            llm_eval_faithfulness_score,
            llm_eval_context_precision_score,
            llm_eval_response_relevancy_score,
            llm_eval_noise_sensitivity_score,
            llm_eval_runs_total,
        )

        label_kwargs = {
            "model": trace.model,
            "prompt_type": trace.prompt_type,
            "retriever": trace.retriever,
            "dataset": trace.dataset,
            "env": trace.env,
            "version": trace.version,
        }
        counter_kwargs = {
            "model": trace.model,
            "env": trace.env,
        }

        timeout = getattr(settings, "LLM_EVAL_TIMEOUT_SECONDS", 30)

        try:
            scores = await asyncio.wait_for(
                self._call_ragas(trace),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "LLMEvaluator: evaluation timed out after %s seconds for model=%s",
                timeout,
                trace.model,
            )
            llm_eval_runs_total.labels(**counter_kwargs, status="error").inc()
            return
        except Exception as exc:
            logger.error(
                "LLMEvaluator: RAGAS evaluation failed for model=%s: %s",
                trace.model,
                exc,
                exc_info=True,
            )
            llm_eval_runs_total.labels(**counter_kwargs, status="error").inc()
            return

        # Export clamped scores to Prometheus gauges
        llm_eval_faithfulness_score.labels(**label_kwargs).set(
            clamp_score(scores["faithfulness"])
        )
        llm_eval_context_precision_score.labels(**label_kwargs).set(
            clamp_score(scores["context_precision"])
        )
        llm_eval_response_relevancy_score.labels(**label_kwargs).set(
            clamp_score(scores["answer_relevancy"])
        )
        llm_eval_noise_sensitivity_score.labels(**label_kwargs).set(
            clamp_score(scores["noise_sensitivity"])
        )

        llm_eval_runs_total.labels(**counter_kwargs, status="success").inc()

    @staticmethod
    async def _call_ragas(trace: RAGTrace) -> dict:
        """Execute RAGAS scoring in a thread pool to avoid blocking the loop."""
        import asyncio
        from ragas import evaluate
        from ragas.metrics import (
            faithfulness,
            context_precision,
            answer_relevancy,
            noise_sensitivity,
        )
        from datasets import Dataset

        def _sync_evaluate() -> dict:
            dataset = Dataset.from_dict(
                {
                    "question": [trace.question],
                    "contexts": [trace.context],
                    "answer": [trace.answer],
                }
            )
            result = evaluate(
                dataset,
                metrics=[faithfulness, context_precision, answer_relevancy, noise_sensitivity],
            )
            row = result.to_pandas().iloc[0]
            return {
                "faithfulness": float(row["faithfulness"]),
                "context_precision": float(row["context_precision"]),
                "answer_relevancy": float(row["answer_relevancy"]),
                "noise_sensitivity": float(row["noise_sensitivity"]),
            }

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_evaluate)


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_evaluator: Optional[LLMEvaluator] = None


def get_evaluator() -> LLMEvaluator:
    """Return the module-level singleton ``LLMEvaluator`` instance."""
    global _evaluator
    if _evaluator is None:
        _evaluator = LLMEvaluator()
    return _evaluator
