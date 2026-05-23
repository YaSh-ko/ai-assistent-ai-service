import json
import logging
from typing import AsyncGenerator, Any, Dict, Optional
from app.interfaces.model_provider import StreamChunk

logger = logging.getLogger(__name__)

class StreamManager:
    """
    Manages streaming responses for chat sessions.
    Formats chunks into a standardized JSON structure.
    """

    @staticmethod
    def format_chunk(type_: str, data: Dict[str, Any]) -> str:
        """Format a chunk as a Server-Sent Event data line."""
        chunk = {
            "type": type_,
            "data": data
        }
        return f"data: {json.dumps(chunk)}\n\n"

    async def stream_generator(
        self,
        session_id: str,
        llm_stream: AsyncGenerator[StreamChunk, None],
        reasoning_steps: Optional[list] = None
    ) -> AsyncGenerator[str, None]:
        """
        Generator that yields formatted SSE chunks.
        
        Args:
            session_id: The session ID.
            llm_stream: The async generator from the LLM provider.
            reasoning_steps: Optional list of reasoning steps to send before the text.
        """
        try:
            # 0. Send processing status
            yield self.format_chunk("processing", {"session_id": session_id, "status": "started"})
            
            # 1. Send reasoning steps if available
            if reasoning_steps:
                for step in reasoning_steps:
                    yield self.format_chunk("reasoning_step", step)

            # 2. Stream LLM content
            async for chunk in llm_stream:
                if chunk.content:
                    yield self.format_chunk("text", {"content": chunk.content})
                
                if chunk.is_final:
                    # Optional: send a specific 'done' or 'finish' event if needed by UI
                    # But usually the stream ending is enough or a specific DONE message
                    pass

            # 3. Send done signal
            yield self.format_chunk("done", {"session_id": session_id})
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Error in stream_generator for session {session_id}: {e}")
            yield self.format_chunk("error", {"message": str(e)})
            yield "data: [DONE]\n\n"
