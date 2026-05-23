from typing import List
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.core.config import settings

class ChunkingService:
    def __init__(self, chunk_size: int = settings.CHUNKING_CONFIG["chunk_size"], chunk_overlap: int = settings.CHUNKING_CONFIG["chunk_overlap"]):
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\nUser:", "\nAI:", "\n\n", "\n", " ", ""]
        )

    def split_text(self, text: str) -> List[str]:
        return self._text_splitter.split_text(text)

    def split_chat_history(self, chat_history: str) -> List[str]:
        """
        Splits chat history into chunks, respecting message boundaries where possible.
        Assumes chat history is formatted with "User:" and "AI:" prefixes or similar.
        """
        # We can use the same splitter as it's already configured with appropriate separators
        # for chat logs ("\nUser:", "\nAI:", etc.)
        return self._text_splitter.split_text(chat_history)
