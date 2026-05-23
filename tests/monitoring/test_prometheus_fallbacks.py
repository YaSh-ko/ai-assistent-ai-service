import builtins
import importlib.util
from pathlib import Path


def _load_module_without_prometheus(module_path: Path, temp_name: str):
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):  # noqa: A002
        if name == "prometheus_client":
            raise ImportError("forced missing prometheus_client")
        return original_import(name, globals, locals, fromlist, level)

    builtins.__import__ = fake_import
    try:
        spec = importlib.util.spec_from_file_location(temp_name, module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        builtins.__import__ = original_import


def test_eval_metrics_fallback_noop():
    module_path = Path(__file__).resolve().parents[2] / "app" / "monitoring" / "eval_metrics.py"
    module = _load_module_without_prometheus(module_path, "temp_eval_metrics_no_prom")

    assert module._PROMETHEUS_AVAILABLE is False
    metric = module.llm_eval_faithfulness_score.labels(model="m", prompt_type="p", retriever="r", dataset="d", env="e", version="v")
    metric.inc()
    metric.dec()
    metric.set(1)
    metric.observe(0.5)
    with metric.time():
        pass


def test_metrics_fallback_noop():
    module_path = Path(__file__).resolve().parents[2] / "app" / "monitoring" / "metrics.py"
    module = _load_module_without_prometheus(module_path, "temp_metrics_no_prom")

    assert module._PROMETHEUS_AVAILABLE is False
    metric = module.ai_requests_total.labels(endpoint="/x", status="ok")
    metric.inc()
    metric.dec()
    metric.set(1)
    metric.observe(1.0)
    with metric.time():
        pass

