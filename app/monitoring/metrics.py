"""
Метрики для мониторинга работы моделей.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from collections import defaultdict
from statistics import mean, stdev
from threading import Lock

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


ai_requests_total = Counter(
    "ai_requests_total",
    "Общее количество запросов к AI-сервису",
    ["endpoint", "status"],
)

ai_request_duration_seconds = Histogram(
    "ai_request_duration_seconds",
    "Время обработки запроса к AI-сервису (секунды)",
    ["endpoint"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)

ai_active_requests = Gauge(
    "ai_active_requests",
    "Количество запросов, обрабатываемых прямо сейчас",
)

ai_model_requests_total = Counter(
    "ai_model_requests_total",
    "Количество вызовов LLM-модели",
    ["model", "status"],
)

ai_model_duration_seconds = Histogram(
    "ai_model_duration_seconds",
    "Время ответа LLM-модели (секунды)",
    ["model"],
    buckets=[1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0],
)

ai_tokens_total = Counter(
    "ai_tokens_total",
    "Суммарное количество токенов",
    ["model", "token_type"],
)

ai_cost_total_rub = Counter(
    "ai_cost_total_rub",
    "Суммарная стоимость запросов к LLM в рублях",
    ["model"],
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Время выполнения запроса к базе данных (секунды)",
    ["db", "operation"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)

db_errors_total = Counter(
    "db_errors_total",
    "Количество ошибок при запросах к базе данных",
    ["db", "operation"],
)

db_active_connections = Gauge(
    "db_active_connections",
    "Текущее количество открытых соединений с БД",
    ["db"],
)

reasoning_executions_total = Counter(
    "reasoning_executions_total",
    "Количество запусков reasoning pipeline",
    ["status"],
)

reasoning_duration_seconds = Histogram(
    "reasoning_duration_seconds",
    "Время выполнения reasoning pipeline (секунды)",
    buckets=[1.0, 2.0, 5.0, 10.0, 20.0, 60.0, 120.0],
)

reasoning_step_duration_seconds = Histogram(
    "reasoning_step_duration_seconds",
    "Время выполнения отдельного шага reasoning pipeline (секунды)",
    ["step"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)


@dataclass
class RequestMetric:
    """Метрика отдельного запроса."""
    model_name: str
    timestamp: float
    latency_ms: float
    tokens: int
    success: bool


@dataclass
class ModelStats:
    """Агрегированная статистика по модели."""
    model_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    avg_tokens_per_request: float = 0.0
    latencies: List[float] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "model_name": self.model_name,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.successful_requests / max(self.total_requests, 1),
            "total_tokens": self.total_tokens,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "min_latency_ms": round(self.min_latency_ms, 2) if self.min_latency_ms != float('inf') else 0,
            "max_latency_ms": round(self.max_latency_ms, 2),
            "avg_tokens_per_request": round(self.avg_tokens_per_request, 2)
        }


class ModelMetrics:
    """
    In-memory метрики для мониторинга работы моделей.
    Thread-safe реализация.
    """
    
    # Singleton instance
    _instance: Optional['ModelMetrics'] = None
    _lock = Lock()
    
    def __new__(cls) -> 'ModelMetrics':
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._stats: Dict[str, ModelStats] = defaultdict(
            lambda: ModelStats(model_name="unknown")
        )
        self._recent_requests: List[RequestMetric] = []
        self._max_recent_requests = 1000
        self._lock = Lock()
        self._initialized = True
    
    def record_request(
        self,
        model_name: str,
        success: bool,
        latency_ms: float,
        tokens: int = 0
    ) -> None:
        """
        Записать метрики запроса.
        
        Args:
            model_name: Имя модели
            success: Успешность запроса
            latency_ms: Время выполнения в мс
            tokens: Количество использованных токенов
        """
        with self._lock:
            if model_name not in self._stats:
                self._stats[model_name] = ModelStats(model_name=model_name)
            
            stats = self._stats[model_name]
            
            stats.total_requests += 1
            if success:
                stats.successful_requests += 1
            else:
                stats.failed_requests += 1
            
            stats.total_tokens += tokens
            stats.total_latency_ms += latency_ms
            
            stats.min_latency_ms = min(stats.min_latency_ms, latency_ms)
            stats.max_latency_ms = max(stats.max_latency_ms, latency_ms)
            
            stats.latencies.append(latency_ms)
            if len(stats.latencies) > 100:
                stats.latencies = stats.latencies[-100:]
            
            stats.avg_latency_ms = stats.total_latency_ms / stats.total_requests
            stats.avg_tokens_per_request = stats.total_tokens / stats.total_requests
            
            metric = RequestMetric(
                model_name=model_name,
                timestamp=time.time(),
                latency_ms=latency_ms,
                tokens=tokens,
                success=success
            )
            self._recent_requests.append(metric)
            
            if len(self._recent_requests) > self._max_recent_requests:
                self._recent_requests = self._recent_requests[-self._max_recent_requests:]
    
    def get_stats(self, model_name: str) -> Optional[ModelStats]:
        """Получить статистику по модели."""
        with self._lock:
            return self._stats.get(model_name)
    
    def get_all_stats(self) -> Dict[str, dict]:
        """Получить статистику по всем моделям."""
        with self._lock:
            return {
                name: stats.to_dict() 
                for name, stats in self._stats.items()
            }
    
    def get_latency_percentiles(
        self, 
        model_name: str
    ) -> Dict[str, float]:
        """Получить перцентили latency для модели."""
        with self._lock:
            stats = self._stats.get(model_name)
            if not stats or not stats.latencies:
                return {}
            
            sorted_latencies = sorted(stats.latencies)
            n = len(sorted_latencies)
            
            return {
                "p50": sorted_latencies[int(n * 0.5)],
                "p90": sorted_latencies[int(n * 0.9)],
                "p95": sorted_latencies[int(n * 0.95)],
                "p99": sorted_latencies[min(int(n * 0.99), n - 1)]
            }
    
    def get_recent_requests(
        self, 
        model_name: Optional[str] = None,
        limit: int = 50
    ) -> List[dict]:
        """Получить недавние запросы."""
        with self._lock:
            requests = self._recent_requests
            if model_name:
                requests = [r for r in requests if r.model_name == model_name]
            
            return [
                {
                    "model_name": r.model_name,
                    "timestamp": r.timestamp,
                    "latency_ms": round(r.latency_ms, 2),
                    "tokens": r.tokens,
                    "success": r.success
                }
                for r in requests[-limit:]
            ]
    
    def get_usage_by_model(self) -> Dict[str, int]:
        """Получить статистику использования моделей."""
        with self._lock:
            return {
                name: stats.total_requests 
                for name, stats in self._stats.items()
            }
    
    def reset(self, model_name: Optional[str] = None) -> None:
        """Сбросить метрики."""
        with self._lock:
            if model_name:
                if model_name in self._stats:
                    self._stats[model_name] = ModelStats(model_name=model_name)
            else:
                self._stats.clear()
                self._recent_requests.clear()
    
    def to_prometheus_format(self) -> str:
        """Экспорт метрик в формате Prometheus."""
        lines = []
        
        with self._lock:
            for name, stats in self._stats.items():
                                
                lines.append(f'model_requests_total{{model="{name}"}} {stats.total_requests}')
                lines.append(f'model_requests_success{{model="{name}"}} {stats.successful_requests}')
                lines.append(f'model_requests_failed{{model="{name}"}} {stats.failed_requests}')
                lines.append(f'model_tokens_total{{model="{name}"}} {stats.total_tokens}')
                lines.append(f'model_latency_avg_ms{{model="{name}"}} {stats.avg_latency_ms:.2f}')
                lines.append(f'model_latency_min_ms{{model="{name}"}} {stats.min_latency_ms:.2f}')
                lines.append(f'model_latency_max_ms{{model="{name}"}} {stats.max_latency_ms:.2f}')
        
        return "\n".join(lines)


@dataclass
class ReasoningStats:
    """Statistics for reasoning process."""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_duration_ms: float = 0.0
    avg_duration_ms: float = 0.0
    step_durations: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    
    def to_dict(self) -> dict:
        return {
            "total_executions": self.total_executions,
            "success_rate": self.successful_executions / max(self.total_executions, 1),
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "step_avg_durations": {
                step: round(mean(durations), 2) if durations else 0
                for step, durations in self.step_durations.items()
            }
        }

class ReasoningMetrics:
    """
    In-memory metrics for reasoning processes.
    Thread-safe implementation.
    """
    
    _instance: Optional['ReasoningMetrics'] = None
    _lock = Lock()
    
    def __new__(cls) -> 'ReasoningMetrics':
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._stats = ReasoningStats()
        self._lock = Lock()
        self._initialized = True
    
    def record_execution(
        self,
        success: bool,
        duration_ms: float,
        step_durations: Dict[str, float]
    ) -> None:
        """Record reasoning execution metrics."""
        with self._lock:
            self._stats.total_executions += 1
            if success:
                self._stats.successful_executions += 1
            else:
                self._stats.failed_executions += 1
                
            self._stats.total_duration_ms += duration_ms
            self._stats.avg_duration_ms = self._stats.total_duration_ms / self._stats.total_executions
            
            for step, duration in step_durations.items():
                self._stats.step_durations[step].append(duration)
                if len(self._stats.step_durations[step]) > 100:
                    self._stats.step_durations[step] = self._stats.step_durations[step][-100:]

    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        with self._lock:
            return self._stats.to_dict()

# Legacy class for backward compatibility
class Metrics:
    """Metrics collection. (Legacy - use ModelMetrics() instead)"""
    pass
