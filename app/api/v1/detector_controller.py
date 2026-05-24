"""
Detector REST endpoints.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_detector_service, get_session_manager
from app.models.detector import (
    DeclineProposalRequest,
    DetectEntitiesRequest,
    DetectorProposal,
    DetectorResult,
)
from app.services.detector_agent import DetectorAgent
from app.services.detector_service import DetectorService, load_session_state
from app.services.session_manager import SessionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["detector"])

_detector_agent = DetectorAgent()


@router.post("/detect-entities", response_model=DetectorResult)
async def detect_entities(
    request: DetectEntitiesRequest,
    session_manager: SessionManager = Depends(get_session_manager),
) -> DetectorResult:
    """
    Analyse recent chat messages and detect entity candidates.
    Used for manual/debug calls; production flow uses run_after_turn in the chat stream.
    """
    session = await session_manager.get_session(request.thread_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    state = load_session_state(session.context or {})
    ctx = request.context.model_copy(update={"session_state": state})

    return await _detector_agent.detect(
        thread_id=request.thread_id,
        messages=request.messages,
        context=ctx,
    )


@router.post("/detector/run/{thread_id}", response_model=Optional[DetectorProposal])
async def run_detector_for_thread(
    thread_id: str,
    detector_service: DetectorService = Depends(get_detector_service),
    session_manager: SessionManager = Depends(get_session_manager),
) -> Optional[DetectorProposal]:
    """Run detector on the latest saved session history (testing / fallback polling)."""
    session = await session_manager.get_session(thread_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = session.history or []
    return await detector_service.run_after_turn(thread_id, messages)


@router.get("/detector/proposal/{thread_id}", response_model=Optional[DetectorProposal])
async def get_detector_proposal(
    thread_id: str,
    detector_service: DetectorService = Depends(get_detector_service),
) -> Optional[DetectorProposal]:
    """Return pending chip proposal if confidence threshold is already met."""
    return await detector_service.get_pending_proposal(thread_id)


@router.post("/detector/decline")
async def decline_detector_proposal(
    request: DeclineProposalRequest,
    detector_service: DetectorService = Depends(get_detector_service),
) -> dict:
    """User dismissed the confirmation chip."""
    ok = await detector_service.decline_proposal(
        request.thread_id,
        title=request.title,
        pending_id=request.pending_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "declined"}
