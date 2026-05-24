"""Tests for GET proposal after chip was already emitted in stream."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.detector import PendingCandidate, SessionState
from app.services.detector_service import DetectorService


@pytest.mark.asyncio
async def test_get_pending_returns_last_proposal_after_chip_shown():
    state = SessionState(
        active=PendingCandidate(
            id="g1",
            type="goal",
            title="Похудеть",
            fields={},
            confidence=0.9,
        ),
        chip_shown_for="g1",
        last_proposal={
            "show_chip": True,
            "action": "confirm_create",
            "entity_type": "goal",
            "confidence": 0.9,
            "pending_id": "g1",
            "preview": {"title": "Похудеть"},
            "revived": False,
        },
    )
    session = MagicMock()
    session.context = {"detector_state": state.model_dump(mode="json")}

    sm = AsyncMock()
    sm.get_session = AsyncMock(return_value=session)

    svc = DetectorService(session_manager=sm)
    proposal = await svc.get_pending_proposal("thread-1")

    assert proposal is not None
    assert proposal.entity_type == "goal"
    assert proposal.pending_id == "g1"
