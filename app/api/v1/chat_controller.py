from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any
import json
import logging
from pydantic import BaseModel

from app.api.deps import get_session_manager, get_rag_chain
from app.chat.session_manager import SessionManager
from app.models.chat_session import ChatSession
from app.models.message import Message
from app.chat.streaming_response import StreamManager
from app.chains.rag_chain import RAGChain
from app.models.response import ChatResponse, ReasoningData, SourceData, ResponseMetadata, RagEvent, ReasoningStep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

class CreateSessionRequest(BaseModel):
    user_id: str

class SendMessageRequest(BaseModel):
    content: str
    role: str = "user"
    model_name: Optional[str] = None

@router.post("/sessions", response_model=ChatSession)
async def create_session(
    request: CreateSessionRequest,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """Create a new chat session."""
    return await session_manager.create_session(request.user_id)

@router.get("/sessions/{session_id}", response_model=ChatSession)
async def get_session(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """Get session details."""
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.get("/sessions/{session_id}/messages", response_model=List[Message])
async def get_history(
    session_id: str,
    limit: int = 50,
    offset: int = 0,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """Get session message history with pagination."""
    return await session_manager.get_history(session_id, limit, offset)

@router.post("/sessions/{session_id}/messages", response_model=ChatResponse)
async def send_message_sync(
    session_id: str,
    request: SendMessageRequest,
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    session_manager: SessionManager = Depends(get_session_manager),
    rag_chain: "RAGChain" = Depends(get_rag_chain)
):
    """
    Send a message and get a synchronous structured response.
    Waits for the full LLM generation.
    """
    if x_session_id and x_session_id != session_id:
        logger.warning(f"Session ID mismatch: path={session_id}, header={x_session_id}")
    
    if not await session_manager.validate_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found or closed")

    await session_manager.save_message(session_id, request.role, request.content)

    try:
        session = await session_manager.get_session(session_id)
        
        llm_stream, state = await rag_chain.process_user_message(
            session_id=session_id,
            user_question=request.content,
            user_id=session.user_id
        )
        
        full_response = ""
        async for chunk in llm_stream:
            if chunk.content:
                full_response += chunk.content
        
        await session_manager.save_message(session_id, "assistant", full_response)
        
        reasoning_steps = []
        for step in state.get("reasoning_steps", []):
            reasoning_steps.append(ReasoningStep(
                step_number=step.get("step_number", 0),
                question=step.get("question"),
                answer=step.get("answer"),
                description=step.get("description"),
                thought=step.get("thought"),
                observation=step.get("observation"),
                sources=step.get("sources", []),
                time_ms=step.get("time_ms")
            ))
            
        reasoning_data = ReasoningData(
            type="simple_qa" if state.get("complexity") == "simple" else "pattern_analysis",
            steps=reasoning_steps,
            confidence_score=state.get("reasoning_metadata", {}).get("confidence"),
            total_time_ms=state.get("reasoning_metadata", {}).get("total_time_ms")
        )
        
        rag_events = []
        for event in state.get("filtered_results", []):
            rag_events.append(RagEvent(
                id=str(event.get("id")) if event.get("id") else None,
                date=str(event.get("event_date")) if event.get("event_date") else None,
                summary=event.get("summary") or event.get("description") or event.get("content", "")[:100],
                title=event.get("title")
            ))
            
        source_data = SourceData(
            rag_events=rag_events,
            cag_selected=[],
            data_sources=["PostgreSQL", "Chroma"] + (["Neo4j"] if state.get("graph_insights") else []),
            graph_insights=state.get("graph_insights", [])
        )
        
        metadata = ResponseMetadata(
            model_used=state.get("selected_model", "unknown"),
            streaming=False,
            session_duration_ms=state.get("processing_time_ms"),
            complexity=state.get("complexity")
        )
        
        return ChatResponse(
            session_id=session_id,
            user_message=request.content,
            assistant_response=full_response,
            reasoning=reasoning_data,
            sources=source_data,
            metadata=metadata
        )

    except Exception as e:
        logger.error(f"Error in sync message generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sessions/{session_id}/stream")
async def send_message_stream(
    session_id: str,
    request: SendMessageRequest,
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    session_manager: SessionManager = Depends(get_session_manager),
    rag_chain: "RAGChain" = Depends(get_rag_chain)
):
    """
    Send a message and get a streaming response (SSE).
    """
    if x_session_id and (x_session_id != session_id):
        logger.warning(f"Session ID mismatch: path={session_id}, header={x_session_id}")

    if not await session_manager.validate_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found or closed")

    await session_manager.save_message(session_id, request.role, request.content)

    stream_manager = StreamManager()

    async def generate():
        full_response = ""
        try:
            session = await session_manager.get_session(session_id)
            
            llm_stream, state = await rag_chain.process_user_message(
                session_id=session_id,
                user_question=request.content,
                user_id=session.user_id
            )
            
            reasoning_steps = state.get("reasoning_steps", [])
            
            async for chunk in stream_manager.stream_generator(session_id, llm_stream, reasoning_steps):
                if chunk.startswith("data: "):
                    try:
                        data_str = chunk[6:].strip()
                        if data_str != "[DONE]":
                            data_json = json.loads(data_str)
                            if data_json["type"] == "text":
                                full_response += data_json["data"]["content"]
                    except Exception as e:
                        raise HTTPException(status_code=500, detail="Failed to process chunk")
                yield chunk

            if full_response:
                await session_manager.save_message(session_id, "assistant", full_response)
                
        except Exception as e:
            logger.error(f"Error in stream generation: {e}")
            yield StreamManager.format_chunk("error", {"message": str(e)})

    return StreamingResponse(generate(), media_type="text/event-stream")

@router.post("/sessions/{session_id}/close")
async def close_session(
    session_id: str,
    session_manager: SessionManager = Depends(get_session_manager)
):
    """Close a session."""
    success = await session_manager.close_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "closed"}
