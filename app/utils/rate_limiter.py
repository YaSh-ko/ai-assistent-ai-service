"""
Simple rate limiter для предотвращения thundering herd при 429 ошибках.
"""
import asyncio
import time
from typing import Optional


class AdaptiveRateLimiter:
    """
    Адаптивный rate limiter, который замедляет запросы при получении 429.
    """
    
    def __init__(self, initial_delay: float = 0.0, max_delay: float = 10.0):
        self._delay = initial_delay
        self._max_delay = max_delay
        self._last_request_time = 0.0
        self._lock = asyncio.Lock()
        self._consecutive_429s = 0
        self._last_429_time = 0.0
    
    async def acquire(self) -> None:
        """Ожидает перед выполнением запроса, если необходимо."""
        async with self._lock:
            if self._delay > 0:
                now = time.time()
                time_since_last = now - self._last_request_time
                
                if time_since_last < self._delay:
                    wait_time = self._delay - time_since_last
                    await asyncio.sleep(wait_time)
            
            self._last_request_time = time.time()
    
    def on_success(self) -> None:
        """Вызывается при успешном запросе - уменьшает задержку."""
        self._consecutive_429s = 0
        # Постепенно уменьшаем задержку
        self._delay = max(0.0, self._delay * 0.5)
    
    def on_rate_limit(self, retry_after: Optional[int] = None) -> None:
        """Вызывается при получении 429 - увеличивает задержку."""
        self._consecutive_429s += 1
        self._last_429_time = time.time()
        
        if retry_after:
            # Используем Retry-After из заголовка
            self._delay = min(retry_after, self._max_delay)
        else:
            # Экспоненциальное увеличение задержки
            self._delay = min(
                self._delay * 2 if self._delay > 0 else 1.0,
                self._max_delay
            )
    
    def should_circuit_break(self) -> bool:
        """
        Проверяет, нужно ли временно прекратить запросы (circuit breaker).
        """
        # Если получили много 429 подряд за короткое время
        if self._consecutive_429s >= 5:
            time_since_last_429 = time.time() - self._last_429_time
            # Если последняя 429 была меньше минуты назад
            if time_since_last_429 < 60:
                return True
        return False
    
    def get_current_delay(self) -> float:
        """Возвращает текущую задержку между запросами."""
        return self._delay
