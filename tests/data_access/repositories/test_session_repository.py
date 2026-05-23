"""
Tests for SessionRepository — 11 uncovered lines.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.data_access.repositories.session_repository import SessionRepository


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def repo(mock_db):
    return SessionRepository(mock_db)


class TestSessionRepository:
    @pytest.mark.asyncio
    async def test_get_session_returns_none(self, repo):
        result = await repo.get_session("s1")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_session_returns_none(self, repo):
        result = await repo.create_session({"session_id": "s1"})
        assert result is None

    @pytest.mark.asyncio
    async def test_update_session_returns_none(self, repo):
        result = await repo.update_session("s1", {"status": "closed"})
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_session_returns_none(self, repo):
        result = await repo.delete_session("s1")
        assert result is None

    def test_repo_stores_database(self, repo, mock_db):
        assert repo.database is mock_db
