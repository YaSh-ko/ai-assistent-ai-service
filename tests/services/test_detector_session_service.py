"""Unit tests for detector session accumulation (active + shelved)."""
import pytest

from app.models.detector import (
    DetectedEntity,
    DetectorResult,
    PendingCandidate,
    ProposedEntity,
    SessionState,
)
from app.services.detector_session_service import DetectorSessionService


@pytest.fixture
def service() -> DetectorSessionService:
    return DetectorSessionService()


def _observation(confidence: float, title: str = "Провал на работе") -> DetectedEntity:
    return DetectedEntity(
        type="observation",
        confidence=confidence,
        title=title,
        fields={"description": "Описание ситуации"},
    )


def _goal(confidence: float, title: str = "Похудеть к лету") -> DetectedEntity:
    return DetectedEntity(
        type="goal",
        confidence=confidence,
        title=title,
        description="Минус 5 кг к июню",
        target_date="2026-06-01",
    )


def test_creates_active_when_above_start_threshold(service: DetectorSessionService):
    state = SessionState()
    detection = DetectorResult(entities=[_observation(0.6)])

    new_state, proposal = service.process_detection(state, detection)

    assert new_state.active is not None
    assert new_state.active.confidence == 0.6
    assert proposal is None


def test_shows_chip_when_confidence_high_enough(service: DetectorSessionService):
    state = SessionState()
    detection = DetectorResult(entities=[_observation(0.9)])

    new_state, proposal = service.process_detection(state, detection)

    assert proposal is not None
    assert proposal.show_chip is True
    assert proposal.entity_type == "observation"
    assert new_state.chip_shown_for == new_state.active.id


def test_reinforces_active_on_same_topic(service: DetectorSessionService):
    active = PendingCandidate(
        id="p1",
        type="observation",
        title="Провал на работе",
        fields={"description": "часть 1"},
        confidence=0.65,
    )
    state = SessionState(active=active)
    detection = DetectorResult(entities=[_observation(0.7)], same_topic_as_pending=True)

    new_state, proposal = service.process_detection(state, detection)

    assert new_state.active.message_count == 2
    assert new_state.active.confidence >= 0.77
    if proposal:
        assert proposal.entity_type == "observation"


def test_chip_after_reinforcement_crosses_threshold(service: DetectorSessionService):
    active = PendingCandidate(
        id="p1",
        type="observation",
        title="Провал на работе",
        fields={},
        confidence=0.78,
    )
    state = SessionState(active=active)
    detection = DetectorResult(entities=[_observation(0.8)], same_topic_as_pending=True)

    _, proposal = service.process_detection(state, detection)

    assert proposal is not None
    assert proposal.show_chip is True


def test_does_not_rechip_same_id_without_revive(service: DetectorSessionService):
    active = PendingCandidate(
        id="p1",
        type="goal",
        title="Похудеть",
        fields={},
        confidence=0.9,
    )
    state = SessionState(active=active, chip_shown_for="p1")
    detection = DetectorResult(
        entities=[_goal(0.92, title="Похудеть")],
        same_topic_as_pending=True,
    )

    _, proposal = service.process_detection(state, detection)

    assert proposal is None


def test_shelves_goal_when_new_event_topic(service: DetectorSessionService):
    goal = PendingCandidate(
        id="g1",
        type="goal",
        title="Похудеть к лету",
        fields={"description": "минус 5 кг"},
        confidence=0.9,
    )
    state = SessionState(active=goal, chip_shown_for="g1")
    detection = DetectorResult(
        entities=[_observation(0.88, title="Срыв на работе — торт")],
        same_topic_as_pending=False,
    )

    new_state, proposal = service.process_detection(state, detection)

    assert len(new_state.shelved) == 1
    assert new_state.shelved[0].id == "g1"
    assert new_state.active.type == "observation"
    assert new_state.active.title.startswith("Срыв")
    assert proposal is not None
    assert proposal.entity_type == "observation"


def test_restores_shelved_goal_on_return(service: DetectorSessionService):
    goal = PendingCandidate(
        id="g1",
        type="goal",
        title="Похудеть к лету",
        fields={"description": "минус 5 кг"},
        confidence=0.9,
    )
    obs = PendingCandidate(
        id="e1",
        type="observation",
        title="Срыв на работе",
        fields={},
        confidence=0.88,
    )
    state = SessionState(active=obs, shelved=[goal], chip_shown_for="e1")
    detection = DetectorResult(
        entities=[_goal(0.85, title="Похудеть к лету")],
        same_topic_as_pending=True,
    )

    new_state, proposal = service.process_detection(state, detection)

    assert new_state.active.id == "g1"
    assert len(new_state.shelved) == 1
    assert new_state.shelved[0].id == "e1"
    assert proposal is not None
    assert proposal is not None
    assert proposal.revived is True
    assert proposal.entity_type == "goal"


def test_decline_clears_active_and_records_title(service: DetectorSessionService):
    active = PendingCandidate(
        id="p1",
        type="goal",
        title="Выучить Python",
        fields={},
        confidence=0.9,
    )
    state = SessionState(active=active)

    new_state = service.decline(state, pending_id="p1")

    assert new_state.active is None
    assert new_state.is_declined("Выучить Python")


def test_same_type_new_goal_shelves_old(service: DetectorSessionService):
    """Second goal in chat (handstand vs weight loss) should shelve first goal."""
    old_goal = PendingCandidate(
        id="g1",
        type="goal",
        title="Похудеть к лету",
        fields={},
        confidence=0.9,
    )
    state = SessionState(active=old_goal, chip_shown_for="g1")
    detection = DetectorResult(
        entities=[_goal(0.88, title="Научиться стоять на руках")],
        same_topic_as_pending=False,
    )

    new_state, proposal = service.process_detection(state, detection)

    assert proposal is not None
    assert proposal.entity_type == "goal"
    assert new_state.active.title == "Научиться стоять на руках"
    assert len(new_state.shelved) == 1
    assert new_state.shelved[0].title == "Похудеть к лету"


def test_topic_switch_emits_chip_despite_same_topic_flag(service: DetectorSessionService):
    """LLM may wrongly set same_topic=true when user switched goal -> event."""
    goal = PendingCandidate(
        id="g1",
        type="goal",
        title="Похудеть к лету",
        fields={},
        confidence=0.92,
    )
    state = SessionState(active=goal, chip_shown_for="g1")
    detection = DetectorResult(
        entities=[_observation(0.88, title="Сорвался на торт на работе")],
        same_topic_as_pending=True,
    )

    new_state, proposal = service.process_detection(state, detection)

    assert proposal is not None
    assert proposal.entity_type == "observation"
    assert new_state.active.type == "observation"
    assert len(new_state.shelved) == 1


def test_skips_declined_titles(service: DetectorSessionService):
    state = SessionState(
        proposed_entities=[
            ProposedEntity(
                type="observation",
                proposed_title="Старый опыт",
                status="declined",
            )
        ]
    )
    detection = DetectorResult(entities=[_observation(0.95, title="Старый опыт")])

    new_state, proposal = service.process_detection(state, detection)

    assert new_state.active is None
    assert proposal is None
