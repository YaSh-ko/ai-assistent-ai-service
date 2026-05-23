"""
Tests for SSEHandler — 5 uncovered lines.
"""
import pytest
from app.streaming.sse_handler import SSEHandler


async def _gen(items):
    for item in items:
        yield item


class TestSSEHandler:
    @pytest.mark.asyncio
    async def test_stream_events_formats_data(self):
        handler = SSEHandler()
        events = [{"type": "text", "content": "hello"}, {"type": "done"}]

        results = []
        async for chunk in handler.stream_events(_gen(events)):
            results.append(chunk)

        assert len(results) == 2
        assert results[0].startswith("data: ")
        assert results[1].startswith("data: ")

    @pytest.mark.asyncio
    async def test_stream_events_empty_generator(self):
        handler = SSEHandler()
        results = []
        async for chunk in handler.stream_events(_gen([])):
            results.append(chunk)
        assert results == []

    @pytest.mark.asyncio
    async def test_stream_events_single_event(self):
        handler = SSEHandler()
        results = []
        async for chunk in handler.stream_events(_gen([{"msg": "hi"}])):
            results.append(chunk)
        assert len(results) == 1
        assert "\n\n" in results[0]
