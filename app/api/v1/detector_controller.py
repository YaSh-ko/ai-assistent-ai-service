"""
Detector endpoint — POST /api/v1/ai/detect-entities
"""
import logging
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_session_manager
from app.chat.session_manager import SessionManager
from app.models.detector import DetectEntitiesRequest, DetectorResult
from app.services.detector_agent import DetectorAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["detector"])

_detector = DetectorAgent()


@router.post("/detect-entities")
async def detect_entities(
    request: DetectEntitiesRequest,
    session_manager: SessionManager = Depends(get_session_manager),
) -> DetectorResult:
    """
    Analyse recent chat messages and detect Event/Concept candidates.
    Called after each assistant response (async, non-blocking).
    """
    session = await session_manager.get_session(request.thread_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await _detector.detect(
        thread_id=request.thread_id,
        messages=request.messages,
        context=request.context,
    )

    # Persist updated session state if detector found something
    if result.has_content():
        detector_state = session.context.get("detector_state", {})
        await session_manager.update_session(
            request.thread_id,
            {"context": {**session.context, "detector_state": detector_state}},
        )

    return result
