"""
LangGraph SDK-compatible Runs API.

Provides run streaming endpoints that agent-chat-ui expects.
Wires up the RAGChain for AI responses.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional, Annotated
from pydantic import BaseModel
from datetime import datetime, timezone
import asyncio
import json
import uuid
import logging

from app.models.run import Run
from app.api.deps import get_detector_service, get_rag_chain, get_session_manager
from app.services.detector_service import DetectorService
from app.services.session_manager import SessionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/threads/{thread_id}/runs", tags=["runs"])


class RunStreamRequest(BaseModel):
    """Request for creating and streaming a run (LangGraph SDK compatible).
    
    The SDK sends this when the user submits a message.
    Key fields:
    - input: { messages: [...] } — the messages to process
    - assistant_id: the assistant/graph to use
    - stream_mode: ["values"] — how to stream responses  
    """
    assistant_id: Optional[str] = None
    input: Optional[Dict[str, Any]] = None
    command: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    stream_mode: Optional[List[str]] = None
    stream_subgraphs: Optional[bool] = None
    feedback_keys: Optional[List[str]] = None
    interrupt_before: Optional[List[str]] = None
    interrupt_after: Optional[List[str]] = None
    checkpoint: Optional[Dict[str, Any]] = None
    checkpoint_id: Optional[str] = None
    webhook: Optional[str] = None
    multitask_strategy: Optional[str] = None
    on_completion: Optional[str] = None
    on_disconnect: Optional[str] = None
    after_seconds: Optional[float] = None
    if_not_exists: Optional[str] = None


def _format_sse(event: str, data: Any) -> str:
    """Format a Server-Sent Event in the LangGraph protocol format."""
    json_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {json_data}\n\n"


def _extract_text_content(content) -> str:
    """Extract text from message content (string or list of blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        return " ".join(text_parts)
    return ""



def _extract_user_message(input_data: Optional[Dict[str, Any]]) -> Optional[str]:
    """Extract user message text from the SDK input format."""
    if not input_data:
        return None
    
    messages = input_data.get("messages", [])
    if not messages:
        return None
    
    # Find the last human message
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("type") == "human":
            return _extract_text_content(msg.get("content", ""))
    return None


def _trim_to_last_human(messages: list) -> list:
    """Trim messages list to end at the last human message (inclusive)."""
    last_human_idx = None
    for i, msg in enumerate(messages):
        if isinstance(msg, dict) and msg.get("type") == "human":
            last_human_idx = i
    if last_human_idx is None:
        return messages
    return messages[: last_human_idx + 1]


async def _get_existing_messages(thread_id: str, session_manager: SessionManager) -> list:
    """Load existing messages for a thread from the database."""
    session = await session_manager.get_session(thread_id)
    if session and session.history:
        return session.history
    return []


def _parse_checkpoint_id(request: RunStreamRequest) -> Optional[str]:
    """Extract checkpoint ID from request."""
    if request.checkpoint:
        return (
            request.checkpoint.get("checkpoint_id")
            if isinstance(request.checkpoint, dict)
            else request.checkpoint_id
        )
    return request.checkpoint_id


async def _handle_regeneration_flow(
    thread_id: str,
    checkpoint_id: str,
    existing_messages: list,
    session_manager: SessionManager
) -> tuple[Optional[str], list]:
    """Handle the logic for replaying from a checkpoint."""
    base_messages = await session_manager.get_messages_by_checkpoint(thread_id, checkpoint_id)
    if not base_messages:
        base_messages = existing_messages
        
    full_messages_history = _trim_to_last_human(base_messages)
    user_message = None
    
    # Extract the question to re-ask
    for msg in reversed(full_messages_history):
        if isinstance(msg, dict) and msg.get("type") == "human":
            user_message = _extract_text_content(msg.get("content", ""))
            break
            
    return user_message, full_messages_history


def _merge_normal_messages(existing_messages: list, input_data: Optional[Dict[str, Any]]) -> list:
    """Merge incoming messages with existing history."""
    new_input_messages = input_data.get("messages", []) if input_data else []
    existing_ids = {m.get("id") for m in existing_messages if isinstance(m, dict) and m.get("id")}
    filtered_new_messages = [
        m for m in new_input_messages
        if not (isinstance(m, dict) and m.get("id") in existing_ids)
    ]
    return existing_messages + filtered_new_messages


async def _generate_and_save_title(
    thread_id: str,
    user_message: str,
    llm_service: Any,
    session_manager: SessionManager,
) -> None:
    """Fire-and-forget: generate a chat title via LLM and persist it to the DB."""
    try:
        from app.services.title_service import generate_title
        title = await generate_title(user_message, llm_service)
        await session_manager.update_session(thread_id, {"title": title})
        logger.info("Title saved for thread %s: %s", thread_id, title)
    except Exception as e:
        logger.error("Failed to save title for thread %s: %s", thread_id, e)


async def _stream_and_save_response(
    thread_id: str,
    run_id: str,
    assistant_id: Optional[str],
    user_message: str,
    user_id: str,
    full_messages_history: list,
    checkpoint_id: Optional[str],
    is_regeneration: bool,
    rag_chain: Any,
    session_manager: SessionManager,
    detector_service: DetectorService,
    is_first_message: bool = False,
):
    """Internal generator to stream RAGChain output and save state."""
    yield _format_sse("metadata", {"run_id": run_id})
    yield _format_sse("values", {"messages": full_messages_history})

    try:
        # Save intermediate state with only human messages (no AI yet).
        # This becomes the parent_checkpoint for the AI response,
        # so regeneration replays from the correct human message.
        if not is_regeneration:
            pre_ai_checkpoint_id = await session_manager.save_thread_state(
                thread_id, run_id, assistant_id,
                full_messages_history,
                parent_checkpoint_id=None
            )
            # Fire-and-forget: generate title for the first message only.
            # Does NOT block the stream — runs concurrently in the background.
            # Stored in a variable to prevent premature garbage collection.
            if is_first_message:
                _title_task = asyncio.create_task(
                    _generate_and_save_title(
                        thread_id, user_message, rag_chain.llm_service, session_manager
                    )
                )
        else:
            pre_ai_checkpoint_id = checkpoint_id

        llm_stream, _ = await rag_chain.process_user_message(
            thread_id=thread_id,
            user_question=user_message,
            user_id=user_id,
        )

        full_response = ""
        ai_message_id = str(uuid.uuid4())
        async for chunk in llm_stream:
            if chunk.content:
                full_response += chunk.content
                yield _format_sse("values", {
                    "messages": full_messages_history + [{"type": "ai", "id": ai_message_id, "content": full_response}]
                })

        if not full_response:
            full_response = "Извините, не удалось сгенерировать ответ."

        final_messages = full_messages_history + [
            {"type": "ai", "id": ai_message_id, "content": full_response}
        ]
        await session_manager.save_thread_state(
            thread_id, run_id, assistant_id,
            final_messages,
            parent_checkpoint_id=pre_ai_checkpoint_id,
        )

        # Detector → LangGraph SDK reads only event: "custom"
        try:
            proposal = await detector_service.run_after_turn(thread_id, final_messages)
            if proposal and proposal.show_chip:
                yield _format_sse(
                    "custom",
                    {
                        "type": "detector_proposal",
                        "proposal": proposal.model_dump(),
                    },
                )
                logger.info(
                    "Detector SSE (custom) thread=%s type=%s",
                    thread_id,
                    proposal.entity_type,
                )
        except Exception as det_err:
            logger.warning(
                "Detector failed for thread %s: %s", thread_id, det_err, exc_info=True
            )
    except Exception as e:
        logger.error(f"Error in _stream_and_save_response: {e}", exc_info=True)
        yield _format_sse("error", {"message": str(e), "name": "StreamError"})


@router.post("/stream")
async def stream_run_create(
    thread_id: str,
    request: RunStreamRequest,
    rag_chain: Annotated[Any, Depends(get_rag_chain)],
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
    detector_service: Annotated[DetectorService, Depends(get_detector_service)],
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    """
    Create a run and stream results (LangGraph SDK compatible).
    
    This is the main endpoint called by agent-chat-ui's useStream() hook.
    POST /threads/{thread_id}/runs/stream
    """
    user_id = x_user_id or "default_user"
    logger.info(f"Stream run for thread {thread_id}, user {user_id}")
    
    existing_messages = await _get_existing_messages(thread_id, session_manager)
    user_message = _extract_user_message(request.input)
    is_regeneration = False
    full_messages_history = []
    checkpoint_id = _parse_checkpoint_id(request)
        
    if not user_message and checkpoint_id:
        is_regeneration = True
        user_message, full_messages_history = await _handle_regeneration_flow(
            thread_id, checkpoint_id, existing_messages, session_manager
        )
    
    if not user_message:
        async def empty_response():
            yield _format_sse("metadata", {"run_id": str(uuid.uuid4())})
            yield _format_sse("values", {"messages": existing_messages})
        
        return StreamingResponse(
            empty_response(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    
    if not is_regeneration:
        full_messages_history = _merge_normal_messages(existing_messages, request.input)
    
    run_id = str(uuid.uuid4())
    is_first_message = not existing_messages and not is_regeneration
    return StreamingResponse(
        _stream_and_save_response(
            thread_id, run_id, request.assistant_id, user_message, user_id,
            full_messages_history, checkpoint_id, is_regeneration,
            rag_chain, session_manager, detector_service,
            is_first_message=is_first_message,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/", response_model=Run)
async def create_run(thread_id: str):
    """Create a run (placeholder)."""
    pass


@router.get("/", response_model=List[Run])
async def get_runs(thread_id: str):
    """List runs for a thread (placeholder)."""
    return []


@router.post("/{run_id}/stream")
async def stream_run_by_id(thread_id: str, run_id: str):
    """Stream a specific run by ID (placeholder)."""
    pass
