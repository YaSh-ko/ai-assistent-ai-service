"""Tests for auto-converting create → update when entity index matches."""
from app.models.detector import DetectedEntity
from app.services.detector_service import apply_existing_entity_update


def test_converts_to_update_on_continuation_and_strong_match():
    entity = DetectedEntity(
        type="observation",
        confidence=0.87,
        title="Успех в выражении блокера на daily",
        fields={"description": "Сказал фразу про блокер"},
        action="create",
    )
    existing = [{
        "entity_id": "a23834a1-8109-4613-91b6-45eb109c3cd6",
        "entity_type": "observation",
        "title": "Замешательство на daily из-за страха",
        "score": 0.896,
    }]
    result = apply_existing_entity_update(
        entity, existing, "К тому про daily: сказал одну фразу",
    )
    assert result.action == "update"
    assert result.existing_entity_id == "a23834a1-8109-4613-91b6-45eb109c3cd6"
    assert "Замешательство" in (result.title or "")


def test_keeps_create_when_score_too_low():
    entity = DetectedEntity(
        type="observation",
        confidence=0.87,
        title="Новая тема",
        action="create",
    )
    existing = [{
        "entity_id": "id-1",
        "entity_type": "observation",
        "title": "Другое",
        "score": 0.70,
    }]
    result = apply_existing_entity_update(entity, existing, "К тому про daily")
    assert result.action == "create"


def test_keeps_create_for_unrelated_topic_without_continuation():
    entity = DetectedEntity(
        type="observation",
        confidence=0.87,
        title="Купил кроссовки",
        action="create",
    )
    existing = [{
        "entity_id": "id-1",
        "entity_type": "observation",
        "title": "Daily",
        "score": 0.83,
    }]
    result = apply_existing_entity_update(entity, existing, "Купил новые кроссовки")
    assert result.action == "create"
