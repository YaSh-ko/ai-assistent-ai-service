from typing import Any, Dict, Optional, List
from datetime import date
from types import SimpleNamespace

from app.interfaces.repositories.i_entry_repository import IEntryRepository
from app.data_access.postgresql.entry_thread_repository import EntryThreadRepository
from app.data_access.postgresql.chat_session_repository import ChatSessionRepository
from app.data_access.repositories.embedding_repository import EmbeddingRepository


class DataAccessLayer:
    def __init__(
        self,
        chat_session_repo: ChatSessionRepository,
        entry_repo: IEntryRepository,
        entry_thread_repo: EntryThreadRepository,
        embedding_repo: EmbeddingRepository,
    ):
        self.chat_session_repo = chat_session_repo
        self.entry_repo = entry_repo
        self.entry_thread_repo = entry_thread_repo
        self.embedding_repo = embedding_repo

    async def save_entry_with_embedding(
        self,
        user_id: str,
        title: str,
        description: str,
        event_date: date,
        thread_id: Optional[str] = None,
        embedding: Optional[List[float]] = None,
    ) -> Any:
        """
        Save entry to PostgreSQL and create embedding in ChromaDB.
        Returns the created entry as an object (SimpleNamespace) to support dot notation.
        """
        entry_dict = await self.entry_repo.create(user_id, title, description, event_date)
        if not entry_dict:
            raise RuntimeError("Failed to create entry in PostgreSQL")

        if embedding is None:
            embedding = [0.0] * 1024

        metadata = {
            "entry_id": str(entry_dict["id"]),
            "user_id": user_id,
            "event_date": str(event_date),
        }
        if thread_id:
            metadata["thread_id"] = thread_id

        page_content = f"{title}\n{description}"

        await self.embedding_repo.add_embedding(
            document_id=str(entry_dict["id"]),
            embedding=embedding,
            metadata=metadata,
            page_content=page_content,
        )

        if thread_id:
            await self.entry_thread_repo.create(entry_dict["id"], thread_id, "BELONGS_TO", user_id)

        return SimpleNamespace(**entry_dict)
