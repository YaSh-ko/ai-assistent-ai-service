from typing import Any, Dict, Optional, List
from datetime import date
from types import SimpleNamespace
import asyncpg

from app.interfaces.repositories.i_session_repository import ISessionRepository
from app.interfaces.repositories.i_entry_repository import IEntryRepository
from app.data_access.postgresql.entry_thread_repository import EntryThreadRepository
from app.data_access.postgresql.goal_thread_repository import GoalThreadRepository
from app.data_access.postgresql.experiment_thread_repository import ExperimentThreadRepository
from app.data_access.postgresql.analysis_thread_repository import AnalysisThreadRepository
from app.data_access.postgresql.chat_session_repository import ChatSessionRepository
from app.data_access.repositories.embedding_repository import EmbeddingRepository
from app.interfaces.vector_store import IVectorStore

class DataAccessLayer:
    def __init__(
        self, 
        session_repo: ISessionRepository,
        chat_session_repo: ChatSessionRepository,
        entry_repo: IEntryRepository,
        entry_thread_repo: EntryThreadRepository,
        goal_thread_repo: GoalThreadRepository,
        experiment_thread_repo: ExperimentThreadRepository,
        analysis_thread_repo: AnalysisThreadRepository,
        embedding_repo: EmbeddingRepository
    ):
        self.session_repo = session_repo
        self.chat_session_repo = chat_session_repo
        self.entry_repo = entry_repo
        self.entry_thread_repo = entry_thread_repo
        self.goal_thread_repo = goal_thread_repo
        self.experiment_thread_repo = experiment_thread_repo
        self.analysis_thread_repo = analysis_thread_repo
        self.embedding_repo = embedding_repo

    async def save_entry_with_embedding(
        self, 
        user_id: str, 
        title: str, 
        description: str, 
        event_date: date, 
        thread_id: Optional[str] = None,
        embedding: Optional[List[float]] = None
    ) -> Any:
        """
        Save entry to PostgreSQL and create embedding in ChromaDB.
        Returns the created entry as an object (SimpleNamespace) to support dot notation.
        """
        # 1. Save to PostgreSQL
        entry_dict = await self.entry_repo.create(user_id, title, description, event_date)
        if not entry_dict:
            raise RuntimeError("Failed to create entry in PostgreSQL")
            
        # 2. Create Embedding
        if embedding is None:
            # Use dummy embedding if not provided (fallback)
            embedding = [0.0] * 1024
        
        metadata = {
            "entry_id": str(entry_dict['id']),
            "user_id": user_id,
            "event_date": str(event_date)
        }
        if thread_id:
            metadata["thread_id"] = thread_id
            
        page_content = f"{title}\n{description}"
        
        await self.embedding_repo.add_embedding(
            document_id=str(entry_dict['id']),
            embedding=embedding,
            metadata=metadata,
            page_content=page_content
        )
        
        # 3. Link to thread if provided
        if thread_id:
            await self.entry_thread_repo.create(entry_dict['id'], thread_id, "BELONGS_TO", user_id)
            
        # Return as object to satisfy test expectation (entry.id)
        return SimpleNamespace(**entry_dict)
