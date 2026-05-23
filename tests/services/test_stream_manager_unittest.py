import unittest
import asyncio
import json
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.services.stream_manager import StreamManager
from app.interfaces.model_provider import StreamChunk

class TestStreamManager(unittest.TestCase):
    def test_format_chunk(self):
        chunk = StreamManager.format_chunk("text", {"content": "hello"})
        expected = 'data: {"type": "text", "data": {"content": "hello"}}\n\n'
        self.assertEqual(chunk, expected)

    async def _run_generator(self):
        # Mock LLM stream
        async def mock_llm_stream():
            yield StreamChunk(content="Hello", is_final=False)
            yield StreamChunk(content=" World", is_final=False)
            yield StreamChunk(content="", is_final=True)

        manager = StreamManager()
        chunks = []
        async for chunk in manager.stream_generator("session1", mock_llm_stream()):
            chunks.append(chunk)
        return chunks

    def test_stream_generator(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        chunks = loop.run_until_complete(self._run_generator())
        loop.close()

        # Verify chunks
        # 1. Text chunks
        self.assertIn('data: {"type": "text", "data": {"content": "Hello"}}\n\n', chunks)
        self.assertIn('data: {"type": "text", "data": {"content": " World"}}\n\n', chunks)
        
        # 2. Done chunk
        self.assertIn('data: {"type": "done", "data": {"session_id": "session1"}}\n\n', chunks)
        
        # 3. SSE Done
        self.assertIn('data: [DONE]\n\n', chunks)

if __name__ == "__main__":
    unittest.main()
