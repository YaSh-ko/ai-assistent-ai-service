"""
Tests for ModelMetrics and ReasoningMetrics — 54 uncovered lines.
"""
import pytest
from app.monitoring.metrics import ModelMetrics, ReasoningMetrics, ModelStats


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset singleton state before each test."""
    m = ModelMetrics()
    m.reset()
    r = ReasoningMetrics()
    with r._lock:
        from app.monitoring.metrics import ReasoningStats
        from collections import defaultdict
        r._stats = ReasoningStats()
    yield


class TestModelMetrics:
    def test_singleton(self):
        a = ModelMetrics()
        b = ModelMetrics()
        assert a is b

    def test_record_request_success(self):
        m = ModelMetrics()
        m.record_request("gpt", success=True, latency_ms=100.0, tokens=50)
        stats = m.get_stats("gpt")
        assert stats.total_requests == 1
        assert stats.successful_requests == 1
        assert stats.failed_requests == 0
        assert stats.total_tokens == 50

    def test_record_request_failure(self):
        m = ModelMetrics()
        m.record_request("gpt", success=False, latency_ms=200.0)
        stats = m.get_stats("gpt")
        assert stats.failed_requests == 1
        assert stats.successful_requests == 0

    def test_avg_latency(self):
        m = ModelMetrics()
        m.record_request("gpt", success=True, latency_ms=100.0)
        m.record_request("gpt", success=True, latency_ms=200.0)
        stats = m.get_stats("gpt")
        assert stats.avg_latency_ms == 150.0

    def test_min_max_latency(self):
        m = ModelMetrics()
        m.record_request("gpt", success=True, latency_ms=50.0)
        m.record_request("gpt", success=True, latency_ms=300.0)
        stats = m.get_stats("gpt")
        assert stats.min_latency_ms == 50.0
        assert stats.max_latency_ms == 300.0

    def test_get_all_stats(self):
        m = ModelMetrics()
        m.record_request("model-a", success=True, latency_ms=10.0, tokens=5)
        m.record_request("model-b", success=False, latency_ms=20.0)
        all_stats = m.get_all_stats()
        assert "model-a" in all_stats
        assert "model-b" in all_stats

    def test_get_latency_percentiles(self):
        m = ModelMetrics()
        for i in range(1, 101):
            m.record_request("gpt", success=True, latency_ms=float(i))
        percentiles = m.get_latency_percentiles("gpt")
        assert "p50" in percentiles
        assert "p90" in percentiles
        assert "p95" in percentiles
        assert "p99" in percentiles

    def test_get_latency_percentiles_empty(self):
        m = ModelMetrics()
        assert m.get_latency_percentiles("nonexistent") == {}

    def test_get_recent_requests(self):
        m = ModelMetrics()
        m.record_request("gpt", success=True, latency_ms=10.0, tokens=3)
        recent = m.get_recent_requests("gpt")
        assert len(recent) == 1
        assert recent[0]["model_name"] == "gpt"

    def test_get_recent_requests_all_models(self):
        m = ModelMetrics()
        m.record_request("a", success=True, latency_ms=1.0)
        m.record_request("b", success=True, latency_ms=2.0)
        recent = m.get_recent_requests()
        assert len(recent) == 2

    def test_get_usage_by_model(self):
        m = ModelMetrics()
        m.record_request("gpt", success=True, latency_ms=1.0)
        m.record_request("gpt", success=True, latency_ms=1.0)
        usage = m.get_usage_by_model()
        assert usage["gpt"] == 2

    def test_reset_specific_model(self):
        m = ModelMetrics()
        m.record_request("gpt", success=True, latency_ms=1.0)
        m.record_request("other", success=True, latency_ms=1.0)
        m.reset("gpt")
        assert m.get_stats("gpt") is None or m.get_stats("gpt").total_requests == 0
        assert m.get_stats("other").total_requests == 1

    def test_reset_all(self):
        m = ModelMetrics()
        m.record_request("gpt", success=True, latency_ms=1.0)
        m.reset()
        assert m.get_all_stats() == {}

    def test_to_prometheus_format(self):
        m = ModelMetrics()
        m.record_request("gpt", success=True, latency_ms=50.0, tokens=10)
        output = m.to_prometheus_format()
        assert "model_requests_total" in output
        assert 'model="gpt"' in output

    def test_model_stats_to_dict(self):
        stats = ModelStats(model_name="test")
        stats.total_requests = 2
        stats.successful_requests = 1
        stats.failed_requests = 1
        stats.total_tokens = 100
        stats.total_latency_ms = 200.0
        stats.avg_latency_ms = 100.0
        stats.min_latency_ms = 50.0
        stats.max_latency_ms = 150.0
        d = stats.to_dict()
        assert d["success_rate"] == 0.5
        assert d["total_tokens"] == 100


class TestReasoningMetrics:
    def test_singleton(self):
        a = ReasoningMetrics()
        b = ReasoningMetrics()
        assert a is b

    def test_record_execution_success(self):
        r = ReasoningMetrics()
        r.record_execution(success=True, duration_ms=100.0, step_durations={"step1": 50.0})
        stats = r.get_stats()
        assert stats["total_executions"] == 1
        assert stats["success_rate"] == 1.0

    def test_record_execution_failure(self):
        r = ReasoningMetrics()
        r.record_execution(success=False, duration_ms=200.0, step_durations={})
        stats = r.get_stats()
        assert stats["total_executions"] == 1
        assert stats["success_rate"] == 0.0

    def test_avg_duration(self):
        r = ReasoningMetrics()
        r.record_execution(success=True, duration_ms=100.0, step_durations={})
        r.record_execution(success=True, duration_ms=200.0, step_durations={})
        stats = r.get_stats()
        assert stats["avg_duration_ms"] == 150.0
