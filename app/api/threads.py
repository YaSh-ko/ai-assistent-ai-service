"""
LangGraph SDK-compatible Threads API.

Provides thread management endpoints that agent-chat-ui expects.
Uses in-memory storage for now (TODO: persist to PostgreSQL).
"""

from fastapi import APIRouter, HTTPException, status, Depends, Header
from typing import List, Dict, Any, Optional, Annotated
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid
import logging

from app.models.thread import Thread
from app.services.session_manager import SessionManager
from app.api.deps import get_session_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/threads", tags=["threads"])

# Constants
THREAD_NOT_FOUND = "Thread not found"
NOT_FOUND_RESPONSE = {status.HTTP_404_NOT_FOUND: {"description": THREAD_NOT_FOUND}}


class ThreadCreateRequest(BaseModel):
    """Request to create a thread."""
    metadata: Optional[Dict[str, Any]] = None
    thread_id: Optional[str] = None
    if_exists: Optional[str] = None


class ThreadSearchRequest(BaseModel):
    """Search threads by metadata (LangGraph SDK compatibility)."""
    metadata: Optional[Dict[str, Any]] = None
    limit: int = Field(default=10, le=100)
    offset: int = 0
    status: Optional[str] = None


class ThreadHistoryRequest(BaseModel):
    """Request thread history."""
    limit: int = 10
    before: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    checkpoint: Optional[Dict[str, Any]] = None


@router.post("/search", response_model=List[Thread])
async def search_threads(
    request: ThreadSearchRequest,
    session_manager: SessionManager = Depends(get_session_manager),
):
    """Search threads by metadata. Used by agent-chat-ui via LangGraph SDK."""
    # NOTE: full metadata filtering not implemented — returns empty list for now
    return []


@router.post("", response_model=Thread)
async def create_thread(
    request: ThreadCreateRequest = ThreadCreateRequest(),
    session_manager: SessionManager = Depends(get_session_manager),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    """Create a new thread in PostgreSQL."""
    user_id = x_user_id or "default_user"
    
    # If thread_id provided, check if exists
    if request.thread_id:
        existing = await session_manager.get_session(request.thread_id)
        if existing and request.if_exists != "overwrite":
            return Thread(
                thread_id=existing.thread_id,
                created_at=existing.created_at,
                metadata=existing.metadata or {},
            )

    # Create new session (which is a conversation in DB)
    # Note: SessionManager.create_session generates a UUID if not provided
    # but we can also use request.thread_id if present.
    
    # We'll use the repository directly via manager if we want to force the thread_id
    # But for now, let's just use the manager's logic.
    session = await session_manager.create_session(user_id)
    
    # If thread_id was requested but manager generated another, we might have a drift
    # but practically the frontend usually doesn't provide one for new threads.
    
    return Thread(
        thread_id=session.thread_id,
        created_at=session.created_at,
        metadata=session.metadata or {},
    )


@router.get("/{thread_id}", response_model=Thread, responses=NOT_FOUND_RESPONSE)
async def get_thread(
    thread_id: str,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """Get thread by ID from PostgreSQL."""
    session = await session_manager.get_session(thread_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=THREAD_NOT_FOUND)
    
    return Thread(
        thread_id=session.thread_id,
        created_at=session.created_at,
        metadata=session.metadata or {},
    )


@router.patch("/{thread_id}", response_model=Thread, responses=NOT_FOUND_RESPONSE)
async def update_thread(
    thread_id: str,
    body: Optional[Dict[str, Any]] = None,
    session_manager: SessionManager = Depends(get_session_manager),
):
    """Update thread title and/or metadata — persists to PostgreSQL."""
    session = await session_manager.get_session(thread_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=THREAD_NOT_FOUND)

    update_data: Dict[str, Any] = {}
    if body:
        if "title" in body:
            update_data["title"] = body["title"]
        if "metadata" in body and isinstance(body["metadata"], dict):
            merged = {**(session.metadata or {}), **body["metadata"]}
            update_data["metadata"] = merged

    if update_data:
        updated = await session_manager.update_session(thread_id, update_data)
        if updated:
            session = updated

    return Thread(
        thread_id=session.thread_id,
        created_at=session.created_at,
        metadata=session.metadata or {},
    )


@router.delete("/{thread_id}", responses=NOT_FOUND_RESPONSE)
async def delete_thread(
    thread_id: str,
    session_manager: SessionManager = Depends(get_session_manager),
):
    """Delete a thread."""
    deleted = await session_manager.repository.delete(thread_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=THREAD_NOT_FOUND)
    # Invalidate cache
    session_manager._cache.pop(thread_id, None)
    return {"status": "ok"}


@router.get("/{thread_id}/state", responses=NOT_FOUND_RESPONSE)
async def get_thread_state(
    thread_id: str,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """
    Get current thread state (LangGraph SDK compatible).
    """
    session_manager._cache.pop(thread_id, None)
    session = await session_manager.get_session(thread_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=THREAD_NOT_FOUND)

    if session.states:
        return session.states[0]

    return {
        "values": {"messages": session.history or []},
        "next": [],
        "checkpoint": {
            "thread_id": thread_id,
            "checkpoint_ns": "",
            "checkpoint_id": str(uuid.uuid4()),
        },
        "parent_checkpoint": None,
        "metadata": session.metadata or {},
        "created_at": session.created_at.isoformat(),
        "tasks": [],
    }


@router.post("/{thread_id}/history", responses=NOT_FOUND_RESPONSE)
async def get_thread_history(
    thread_id: str, 
    request: ThreadHistoryRequest = ThreadHistoryRequest(),
    session_manager: SessionManager = Depends(get_session_manager)
):
    """
    Get thread state history (LangGraph SDK compatible).
    """
    session_manager._cache.pop(thread_id, None)
    session = await session_manager.get_session(thread_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=THREAD_NOT_FOUND)

    if session.states:
        # Paginating the states
        start = 0  # In a real app we'd use request.before/offset
        end = min(len(session.states), start + request.limit)
        return session.states[start:end]

    return []
