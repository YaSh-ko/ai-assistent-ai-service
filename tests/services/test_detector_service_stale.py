"""Tests for stale-entity filter and sleep-thread continuation scenario."""
from app.models.detector import DetectedEntity
from app.services.detector_service import (
    apply_existing_entity_update,
    entity_matches_last_user_message,
)


def test_stale_filter_accepts_token_with_trailing_comma():
    entity = DetectedEntity(
        type="observation",
        confidence=1.0,
        title="Проблема со сном продолжается",
        fields={
            "description": (
                "Пользователь продолжает испытывать трудности "
                "с ранним отходом ко сну и недосыпанием."
            ),
        },
    )
    msg = (
        "Возвращаясь ко сну, сегодня уже не получилось лечь, "
        "также поздно лег, и снова не выспался"
    )
    assert entity_matches_last_user_message(entity, msg) is True


def test_auto_update_when_same_topic_and_semantic_match():
    entity = DetectedEntity(
        type="observation",
        confidence=1.0,
        title="Проблема со сном продолжается",
        fields={"description": "Снова поздно лег", "valence": -0.5},
        action="create",
    )
    existing = [{
        "entity_id": "718f7636-3a75-4b96-831e-a9796b0d3482",
        "entity_type": "observation",
        "title": "Недосып влияет на продуктивность и концентрацию",
        "description": "Поздний отход ко сну, не высыпается",
        "score": 0.871,
    }]
    result = apply_existing_entity_update(
        entity, existing, "Возвращаясь ко сну, сегодня снова поздно лег",
    )
    assert result.action == "update"
    assert result.existing_entity_id == "718f7636-3a75-4b96-831e-a9796b0d3482"


def test_no_auto_update_without_same_topic_and_moderate_score():
    entity = DetectedEntity(
        type="observation",
        confidence=0.9,
        title="Новая тема",
        action="create",
    )
    existing = [{
        "entity_id": "id-1",
        "entity_type": "observation",
        "title": "Недосып",
        "score": 0.871,
    }]
    result = apply_existing_entity_update(
        entity, existing, "Купил новые кроссовки",
    )
    assert result.action == "create"


def test_no_auto_update_when_embedding_similar_but_unrelated_message():
    """Chroma may score ~0.85 on vague personal topics; LLM same_topic must not force update."""
    entity = DetectedEntity(
        type="observation",
        confidence=0.85,
        title="Проблемы со стиркой одежды и забралом заказа на Wildberries",
        fields={"description": "Не постирал и не забрал заказ"},
        action="create",
    )
    existing = [{
        "entity_id": "5718ee3a-7185-468c-9420-a056856c7478",
        "entity_type": "observation",
        "title": "Поздний сон перед встречей",
        "score": 0.858,
    }]
    msg = (
        "я так устал, нет одежды на завтра, не постирал, "
        "на вайлдбериз не забрал заказ"
    )
    result = apply_existing_entity_update(entity, existing, msg)
    assert result.action == "create"
