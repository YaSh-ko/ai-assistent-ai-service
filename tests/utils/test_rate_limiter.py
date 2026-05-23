"""
Тесты для AdaptiveRateLimiter
"""
import asyncio
import pytest
import time
from app.utils.rate_limiter import AdaptiveRateLimiter


@pytest.mark.asyncio
async def test_initial_no_delay():
    """Первый запрос не должен иметь задержки"""
    limiter = AdaptiveRateLimiter(initial_delay=0.0)
    
    start = time.time()
    await limiter.acquire()
    elapsed = time.time() - start
    
    assert elapsed < 0.1  # Практически без задержки


@pytest.mark.asyncio
async def test_rate_limit_increases_delay():
    """При 429 задержка должна увеличиваться"""
    limiter = AdaptiveRateLimiter(initial_delay=0.0, max_delay=10.0)
    
    # Первая 429
    limiter.on_rate_limit()
    assert limiter.get_current_delay() > 0
    
    first_delay = limiter.get_current_delay()
    
    # Вторая 429
    limiter.on_rate_limit()
    second_delay = limiter.get_current_delay()
    
    assert second_delay > first_delay  # Экспоненциальный рост


@pytest.mark.asyncio
async def test_success_decreases_delay():
    """При успехе задержка должна уменьшаться"""
    limiter = AdaptiveRateLimiter(initial_delay=0.0)
    
    # Создаем задержку
    limiter.on_rate_limit()
    limiter.on_rate_limit()
    
    delay_before = limiter.get_current_delay()
    
    # Успешный запрос
    limiter.on_success()
    delay_after = limiter.get_current_delay()
    
    assert delay_after < delay_before


@pytest.mark.asyncio
async def test_circuit_breaker_activates():
    """Circuit breaker должен активироваться после многих 429"""
    limiter = AdaptiveRateLimiter()
    
    # Много 429 подряд
    for _ in range(5):
        limiter.on_rate_limit()
    
    assert limiter.should_circuit_break() is True


@pytest.mark.asyncio
async def test_circuit_breaker_resets():
    """Circuit breaker должен сбрасываться со временем"""
    limiter = AdaptiveRateLimiter()
    
    # Активируем circuit breaker
    for _ in range(5):
        limiter.on_rate_limit()
    
    assert limiter.should_circuit_break() is True
    
    # Ждем больше минуты (симулируем)
    limiter._last_429_time = time.time() - 61
    
    assert limiter.should_circuit_break() is False


@pytest.mark.asyncio
async def test_retry_after_respected():
    """Retry-After заголовок должен использоваться"""
    limiter = AdaptiveRateLimiter(max_delay=10.0)
    
    # API говорит подождать 5 секунд
    limiter.on_rate_limit(retry_after=5)
    
    assert limiter.get_current_delay() == 5.0


@pytest.mark.asyncio
async def test_max_delay_respected():
    """Задержка не должна превышать max_delay"""
    limiter = AdaptiveRateLimiter(max_delay=5.0)
    
    # Много 429 подряд
    for _ in range(10):
        limiter.on_rate_limit()
    
    assert limiter.get_current_delay() <= 5.0


@pytest.mark.asyncio
async def test_concurrent_acquire():
    """Несколько одновременных acquire должны работать корректно"""
    limiter = AdaptiveRateLimiter(initial_delay=0.1)
    
    async def do_acquire():
        await limiter.acquire()
        return time.time()
    
    # Запускаем 3 запроса одновременно
    results = await asyncio.gather(
        do_acquire(),
        do_acquire(),
        do_acquire()
    )
    
    # Они должны выполниться последовательно с задержкой
    assert results[1] >= results[0] + 0.1
    assert results[2] >= results[1] + 0.1
