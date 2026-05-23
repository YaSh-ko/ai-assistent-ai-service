import logging
from typing import AsyncGenerator, Any, Dict, Optional, Tuple
from datetime import datetime

from app.chains.rag_chain import RAGChain

logger = logging.getLogger(__name__)

class ChatService:
    """
    Service for processing user messages and orchestrating the RAG pipeline.
    """

    def __init__(self, rag_chain: RAGChain):
        self.rag_chain = rag_chain

    async def process_message(
        self,
        session_id: str,
        user_question: str,
        user_id: str,
        thread_id: Optional[str] = None
    ) -> Tuple[AsyncGenerator[Any, None], Dict[str, Any]]:
        """
        Process a user message using the RAG chain.
        
        Args:
            session_id: The session ID.
            user_question: The user's question.
            user_id: The user's ID.
            thread_id: Optional thread ID.
            
        Returns:
            A tuple of (llm_stream, state).
        """
        logger.info(f"Processing message for session {session_id}")
        return await self.rag_chain.process_user_message(
            session_id=session_id,
            user_question=user_question,
            user_id=user_id,
            thread_id=thread_id
        )
