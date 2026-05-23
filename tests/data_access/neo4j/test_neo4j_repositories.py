"""
Tests for Neo4j repositories:
  AffectRepository    — 32 uncovered lines
  GoalRepository      — 35 uncovered lines
  ConceptRepository   — 33 uncovered lines
  ExperimentRepository— 35 uncovered lines
  AnalysisRepository  — 27 uncovered lines
  EventRepository     — 27 uncovered lines
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from app.data_access.neo4j.affect_repository import AffectRepository
from app.data_access.neo4j.goal_repository import GoalRepository
from app.data_access.neo4j.concept_repository import ConceptRepository
from app.data_access.neo4j.experiment_repository import ExperimentRepository
from app.data_access.neo4j.analysis_repository import AnalysisRepository
from app.data_access.neo4j.event_repository import EventRepository


# ---------------------------------------------------------------------------
# Shared mock DB fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute_read = AsyncMock(return_value=[])
    db.execute_write = AsyncMock(return_value={"nodes_deleted": 1, "properties_set": 1, "relationships_deleted": 1})
    return db


# ===========================================================================
# AffectRepository
# ===========================================================================

class TestAffectRepository:
    @pytest.fixture
    def repo(self, mock_db):
        return AffectRepository(mock_db)

    @pytest.mark.asyncio
    async def test_create_affect_returns_id(self, repo):
        result = await repo.create_affect("a1", "Joy", "u1", 0.8, 0.6)
        assert result == "a1"
        repo.db.execute_write.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_affect_found(self, repo, mock_db):
        mock_db.execute_read = AsyncMock(return_value=[{"a": {"id": "a1", "name": "Joy"}}])
        result = await repo.get_affect("a1")
        assert result["id"] == "a1"

    @pytest.mark.asyncio
    async def test_get_affect_not_found(self, repo):
        result = await repo.get_affect("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_affect_by_name_found(self, repo, mock_db):
        mock_db.execute_read = AsyncMock(return_value=[{"a": {"name": "Joy"}}])
        result = await repo.get_affect_by_name("Joy", "u1")
        assert result["name"] == "Joy"

    @pytest.mark.asyncio
    async def test_get_affect_by_name_not_found(self, repo):
        result = await repo.get_affect_by_name("Unknown", "u1")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_affect_with_properties(self, repo):
        result = await repo.update_affect("a1", {"valence": 0.9})
        assert result is True

    @pytest.mark.asyncio
    async def test_update_affect_empty_properties(self, repo):
        result = await repo.update_affect("a1", {})
        assert result is False
        repo.db.execute_write.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_affect(self, repo):
        result = await repo.delete_affect("a1")
        assert result is True

    @pytest.mark.asyncio
    async def test_find_by_user(self, repo, mock_db):
        mock_db.execute_read = AsyncMock(return_value=[{"a": {"id": "a1"}}, {"a": {"id": "a2"}}])
        results = await repo.find_by_user("u1")
        assert len(results) == 2


# ===========================================================================
# GoalRepository
# ===========================================================================

class TestGoalRepository:
    @pytest.fixture
    def repo(self, mock_db):
        return GoalRepository(mock_db)

    @pytest.mark.asyncio
    async def test_create_goal_returns_id(self, repo):
        result = await repo.create_goal("g1", "Learn Python", "u1", "active")
        assert result == "g1"

    @pytest.mark.asyncio
    async def test_create_goal_with_optional_fields(self, repo):
        result = await repo.create_goal(
            "g2", "Read book", "u1", "active",
            description="Read 10 pages/day",
            priority="high",
            target_date=datetime(2026, 12, 31)
        )
        assert result == "g2"

    @pytest.mark.asyncio
    async def test_get_goal_found(self, repo, mock_db):
        mock_db.execute_read = AsyncMock(return_value=[{"g": {"id": "g1"}}])
        result = await repo.get_goal("g1")
        assert result["id"] == "g1"

    @pytest.mark.asyncio
    async def test_get_goal_not_found(self, repo):
        result = await repo.get_goal("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_goal_with_properties(self, repo):
        result = await repo.update_goal("g1", {"status": "completed"})
        assert result is True

    @pytest.mark.asyncio
    async def test_update_goal_empty_properties(self, repo):
        result = await repo.update_goal("g1", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_goal(self, repo):
        result = await repo.delete_goal("g1")
        assert result is True

    @pytest.mark.asyncio
    async def test_find_by_user_no_status(self, repo, mock_db):
        mock_db.execute_read = AsyncMock(return_value=[{"g": {"id": "g1"}}])
        results = await repo.find_by_user("u1")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_find_by_user_with_status(self, repo, mock_db):
        mock_db.execute_read = AsyncMock(return_value=[{"g": {"id": "g1"}}])
        results = await repo.find_by_user("u1", status="active")
        assert len(results) == 1
        call_params = mock_db.execute_read.call_args[0][1]
        assert call_params["status"] == "active"

    @pytest.mark.asyncio
    async def test_find_by_priority(self, repo, mock_db):
        mock_db.execute_read = AsyncMock(return_value=[{"g": {"id": "g1"}}])
        results = await repo.find_by_priority("u1", "high")
        assert len(results) == 1


# ===========================================================================
# ConceptRepository
# ===========================================================================

class TestConceptRepository:
    @pytest.fixture
    def repo(self, mock_db):
        return ConceptRepository(mock_db)

    @pytest.mark.asyncio
    async def test_create_concept_returns_id(self, repo):
        result = await repo.create_concept("c1", "Stoicism", "u1", "Ancient philosophy", 0.9)
        assert result == "c1"

    @pytest.mark.asyncio
    async def test_get_concept_found(self, repo, mock_db):
        mock_db.execute_read = AsyncMock(return_value=[{"c": {"id": "c1"}}])
        result = await repo.get_concept("c1")
        assert result["id"] == "c1"

    @pytest.mark.asyncio
    async def test_get_concept_not_found(self, repo):
        result = await repo.get_concept("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_concept_by_name_found(self, repo, mock_db):
        mock_db.execute_read = AsyncMock(return_value=[{"c": {"name": "Stoicism"}}])
        result = await repo.get_concept_by_name("Stoicism", "u1")
        assert result["name"] == "Stoicism"

    @pytest.mark.asyncio
    async def test_get_concept_by_name_not_found(self, repo):
        result = await repo.get_concept_by_name("Unknown", "u1")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_concept_with_properties(self, repo):
        result = await repo.update_concept("c1", {"relevance": 0.95})
        assert result is True

    @pytest.mark.asyncio
    async def test_update_concept_empty_properties(self, repo):
        result = await repo.update_concept("c1", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_concept(self, repo):
        result = await repo.delete_concept("c1")
        assert result is True

    @pytest.mark.asyncio
    async def test_find_by_user(self, repo, mock_db):
        mock_db.execute_read = AsyncMock(return_value=[{"c": {"id": "c1"}}, {"c": {"id": "c2"}}])
        results = await repo.find_by_user("u1")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_top_concepts_delegates_to_find_by_user(self, repo, mock_db):
        mock_db.execute_read = AsyncMock(return_value=[{"c": {"id": "c1"}}])
        results = await repo.get_top_concepts("u1", limit=3)
        assert len(results) == 1


# ===========================================================================
# ExperimentRepository
# ===========================================================================

class TestExperimentRepository:
    @pytest.fixture
    def repo(self, mock_db):
        return ExperimentRepository(mock_db)

    @pytest.mark.asyncio
    async def test_create_experiment_returns_id(self, repo):
        result = await repo.create_experiment("ex1", "Cold shower", "u1", "active")
        assert result == "ex1"

    @pytest.mark.asyncio
    async def test_create_experiment_with_dates(self, repo):
        result = await repo.create_experiment(
            "ex2", "Meditation", "u1", "active",
            started_at=datetime(2026, 1, 1),
            ended_at=datetime(2026, 2, 1),
        )
        assert result == "ex2"

    @pytest.mark.asyncio
    async def test_get_experiment_found(self, repo, mock_db):
        mock_db.execute_read = AsyncMock(return_value=[{"e": {"id": "ex1"}}])
        result = await repo.get_experiment("ex1")
        assert result["id"] == "ex1"

    @pytest.mark.asyncio
    async def test_get_experiment_not_found(self, repo):
        result = await repo.get_experiment("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_experiment_with_properties(self, repo):
        result = await repo.update_experiment("ex1", {"status": "completed"})
        assert result is True

    @pytest.mark.asyncio
    async def test_update_experiment_empty_properties(self, repo):
        result = await repo.update_experiment("ex1", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_experiment(self, repo):
        result = await repo.delete_experiment("ex1")
        assert result is True

    @pytest.mark.asyncio
    async def test_find_by_user_no_status(self, repo, mock_db):
        mock_db.execute_read = AsyncMock(return_value=[{"e": {"id": "ex1"}}])
        results = await repo.find_by_user("u1")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_find_active(self, repo, mock_db):
        mock_db.execute_read = AsyncMock(return_value=[{"e": {"id": "ex1"}}])
        results = await repo.find_active("u1")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_complete_experiment(self, repo):
        result = await repo.complete_experiment("ex1", "success", 1, datetime.now())
        assert result is True


# ===========================================================================
# AnalysisRepository
# ===========================================================================

class TestAnalysisRepository:
    @pytest.fixture
    def repo(self, mock_db):
        return AnalysisRepository(mock_db)

    @pytest.mark.asyncio
    async def test_create_analysis_returns_id(self, repo):
        result = await repo.create_analysis("an1", "Weekly review", "u1", "content here")
        assert result == "an1"

    @pytest.mark.asyncio
    async def test_create_analysis_with_optional_fields(self, repo):
        result = await repo.create_analysis(
            "an2", "Monthly", "u1", "content",
            summary="short summary",
            analyzed_at=datetime(2026, 3, 1)
        )
        assert result == "an2"

    @pytest.mark.asyncio
    async def test_get_analysis_found(self, repo, mock_db):
        mock_db.execute_read = AsyncMock(return_value=[{"a": {"id": "an1"}}])
        result = await repo.get_analysis("an1")
        assert result["id"] == "an1"

    @pytest.mark.asyncio
    async def test_get_analysis_not_found(self, repo):
        result = await repo.get_analysis("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_analysis_with_properties(self, repo):
        result = await repo.update_analysis("an1", {"summary": "updated"})
        assert result is True

    @pytest.mark.asyncio
    async def test_update_analysis_empty_properties(self, repo):
        result = await repo.update_analysis("an1", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_analysis(self, repo):
        result = await repo.delete_analysis("an1")
        assert result is True

    @pytest.mark.asyncio
    async def test_find_by_user(self, repo, mock_db):
        mock_db.execute_read = AsyncMock(return_value=[{"a": {"id": "an1"}}])
        results = await repo.find_by_user("u1")
        assert len(results) == 1


# ===========================================================================
# EventRepository
# ===========================================================================

class TestEventRepository:
    @pytest.fixture
    def repo(self, mock_db):
        return EventRepository(mock_db)

    @pytest.mark.asyncio
    async def test_create_event_returns_id(self, repo):
        result = await repo.create_event("ev1", "Meeting", "u1", datetime(2026, 3, 15), 0.8)
        assert result == "ev1"

    @pytest.mark.asyncio
    async def test_get_event_found(self, repo, mock_db):
        mock_db.execute_read = AsyncMock(return_value=[{"e": {"id": "ev1"}}])
        result = await repo.get_event("ev1")
        assert result["id"] == "ev1"

    @pytest.mark.asyncio
    async def test_get_event_not_found(self, repo):
        result = await repo.get_event("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_event_with_properties(self, repo):
        result = await repo.update_event("ev1", {"importance": 0.9})
        assert result is True

    @pytest.mark.asyncio
    async def test_update_event_empty_properties(self, repo):
        result = await repo.update_event("ev1", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_event(self, repo):
        result = await repo.delete_event("ev1")
        assert result is True

    @pytest.mark.asyncio
    async def test_find_by_user(self, repo, mock_db):
        mock_db.execute_read = AsyncMock(return_value=[{"e": {"id": "ev1"}}, {"e": {"id": "ev2"}}])
        results = await repo.find_by_user("u1")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_find_by_user_empty(self, repo):
        results = await repo.find_by_user("u1")
        assert results == []
