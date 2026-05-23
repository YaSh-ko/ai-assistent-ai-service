from typing import Any, AsyncGenerator, Dict

class SSEHandler:
    """Handler for Server-Sent Events."""
    
    async def stream_events(self, event_generator: AsyncGenerator[Dict[str, Any], None]):
        async for event in event_generator:
            yield f"data: {event}\n\n"
