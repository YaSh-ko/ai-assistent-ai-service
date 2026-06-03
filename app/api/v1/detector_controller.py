"""
Detector REST endpoints.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_detector_service, get_entity_index, get_session_manager
from app.models.detector import (
    DeclineProposalRequest,
    DetectorProposal,
)
from app.services.detector_service import DetectorService
from app.services.entity_index_service import EntityIndexService
from app.services.session_manager import SessionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["detector"])


class SimilarEntitiesRequest(BaseModel):
    user_id: str
    query_text: str
    exclude_id: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=20)
    threshold: float = Field(default=0.65, ge=0.0, le=1.0)


class ReindexEntitiesRequest(BaseModel):
    user_id: str


class SimilarEntityItem(BaseModel):
    entity_id: str
    entity_type: str
    title: str
    description: str
    score: float
    life_area: Optional[str] = None


class SimilarEntitiesResponse(BaseModel):
    items: List[SimilarEntityItem]


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


@router.post("/reindex-entities")
async def reindex_entities(
    request: ReindexEntitiesRequest,
    entity_index: EntityIndexService = Depends(get_entity_index),
) -> dict:
    """Полная переиндексация сущностей пользователя в Chroma (после миграций / backfill)."""
    logger.info("[ReindexEntities] user=%s", request.user_id)
    count = await entity_index.force_reindex_user(request.user_id)
    logger.info("[ReindexEntities] user=%s indexed=%d", request.user_id, count)
    return {"status": "ok", "indexed": count}


@router.post("/similar-entities", response_model=SimilarEntitiesResponse)
async def find_similar_entities(
    request: SimilarEntitiesRequest,
    entity_index: EntityIndexService = Depends(get_entity_index),
) -> SimilarEntitiesResponse:
    """Find entities semantically similar to query_text via embeddings."""
    logger.info(
        "[SimilarEntities] === Request === user=%s exclude=%s top_k=%d threshold=%.2f query=%r",
        request.user_id,
        (request.exclude_id or "")[:8] or "-",
        request.top_k,
        request.threshold,
        request.query_text[:120],
    )
    matches = await entity_index.search(
        user_id=request.user_id,
        query_text=request.query_text,
        top_k=request.top_k,
        threshold=request.threshold,
    )

    items = []
    skipped_self = 0
    for m in matches:
        if request.exclude_id and m.entity_id == request.exclude_id:
            skipped_self += 1
            logger.info(
                "[SimilarEntities]   skip self: id=%s score=%.3f title=%r",
                m.entity_id[:8],
                m.score,
                (m.title or "")[:50],
            )
            continue
        items.append(SimilarEntityItem(
            entity_id=m.entity_id,
            entity_type=m.entity_type,
            title=m.title,
            description=m.description,
            score=m.score,
            life_area=m.life_area,
        ))

    logger.info(
        "[SimilarEntities] === Response === chroma_passed=%d skipped_self=%d "
        "returned=%d (for linker)",
        len(matches),
        skipped_self,
        len(items),
    )
    for i, item in enumerate(items, start=1):
        logger.info(
            "[SimilarEntities]   #%d score=%.3f [%s] id=%s area=%s title=%r",
            i,
            item.score,
            item.entity_type,
            item.entity_id[:8],
            item.life_area or "-",
            (item.title or "")[:50],
        )
    return SimilarEntitiesResponse(items=items)
