"""Tests for AI goal task suggestion parsing."""
import pytest

from app.api.v1.insights_controller import (
    SuggestGoalTasksRequest,
    _fallback_tasks,
    _parse_suggested_tasks,
)


def test_parse_suggested_tasks_from_json_fence():
    raw = """```json
{"tasks": [
  {"title": "Пройти вводный курс", "phase": "now"},
  {"title": "Сделать мини-проект", "phase": "next", "description": "Закрепить навык"}
]}
```"""
    tasks = _parse_suggested_tasks(raw)
    assert len(tasks) == 2
    assert tasks[0].title == "Пройти вводный курс"
    assert tasks[0].phase == "now"
    assert tasks[1].phase == "next"
    assert tasks[1].description == "Закрепить навык"


def test_parse_suggested_tasks_normalizes_invalid_phase():
    raw = '{"tasks": [{"title": "Отправить 2 письма менторам на этой неделе", "phase": "later"}]}'
    tasks = _parse_suggested_tasks(raw)
    assert tasks[0].phase == "now"


def test_parse_rejects_vague_tasks():
    raw = '{"tasks": [{"title": "Составить план обучения на месяц", "phase": "now"}]}'
    assert _parse_suggested_tasks(raw) == []


def test_fallback_tasks_non_empty():
    tasks = _fallback_tasks("Выучить Python")
    assert len(tasks) >= 4
    assert all(t.title for t in tasks)


def test_build_goal_prompt_includes_existing():
    from app.api.v1.insights_controller import _build_goal_tasks_prompt

    prompt = _build_goal_tasks_prompt(
        SuggestGoalTasksRequest(
            title="Марафон",
            description="Пробежать 10 км",
            existing_tasks=[{"title": "Купить кроссовки", "status": "pending", "phase": "now"}],
        )
    )
    assert "Марафон" in prompt
    assert "Купить кроссовки" in prompt
