from typing import List, Dict

class ContextService:
    """Service for managing context."""
    
    def format_context(self, messages: List[Dict[str, str]]) -> str:
        # Format messages into a context string
        return "\n".join([f"{m['role']}: {m['content']}" for m in messages])
