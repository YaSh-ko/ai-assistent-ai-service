"""
Tests for postgresql EntryRepository — 30 uncovered lines.
"""
import pytest
from datetime import date
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def provider():
    p = MagicMock()
    p.pool = AsyncMock()
    return p


@pytest.fixture
def repo(provider):
    from app.data_access.postgresql.entry_repository import EntryRepository
    return EntryRepository(provider)


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_returns_entry(self, repo):
        expected = {"id": str(uuid4()), "title": "Test", "description": "desc", "user_id": "u1"}
        repo.fetch_one = AsyncMock(return_value=expected)

        result = await repo.create("u1", "Test", "desc", date.today())
        assert result == expected
        repo.fetch_one.assert_called_once()


class TestGetById:
    @pytest.mark.asyncio
    async def test_get_by_id_found(self, repo):
        entry_id = uuid4()
        expected = {"id": str(entry_id), "title": "Test"}
        repo.fetch_one = AsyncMock(return_value=expected)

        result = await repo.get_by_id(entry_id)
        assert result == expected

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repo):
        repo.fetch_one = AsyncMock(return_value=None)
        result = await repo.get_by_id(uuid4())
        assert result is None


class TestGetByIds:
    @pytest.mark.asyncio
    async def test_get_by_ids_returns_list(self, repo):
        ids = [uuid4(), uuid4()]
        expected = [{"id": str(i)} for i in ids]
        repo.fetch_all = AsyncMock(return_value=expected)

        result = await repo.get_by_ids(ids)
        assert result == expected

    @pytest.mark.asyncio
    async def test_get_by_ids_empty_returns_empty(self, repo):
        result = await repo.get_by_ids([])
        assert result == []


class TestUpdate:
    @pytest.mark.asyncio
    async def test_update_description(self, repo):
        entry_id = uuid4()
        expected = {"id": str(entry_id), "description": "new desc"}
        repo.fetch_one = AsyncMock(return_value=expected)

        result = await repo.update(entry_id, description="new desc")
        assert result["description"] == "new desc"

    @pytest.mark.asyncio
    async def test_update_title(self, repo):
        entry_id = uuid4()
        expected = {"id": str(entry_id), "title": "new title"}
        repo.fetch_one = AsyncMock(return_value=expected)

        result = await repo.update(entry_id, title="new title")
        assert result["title"] == "new title"

    @pytest.mark.asyncio
    async def test_update_event_date(self, repo):
        entry_id = uuid4()
        new_date = date(2025, 1, 1)
        expected = {"id": str(entry_id), "event_date": new_date}
        repo.fetch_one = AsyncMock(return_value=expected)

        result = await repo.update(entry_id, event_date=new_date)
        assert result["event_date"] == new_date

    @pytest.mark.asyncio
    async def test_update_no_fields_returns_existing(self, repo):
        entry_id = uuid4()
        existing = {"id": str(entry_id), "title": "unchanged"}
        repo.get_by_id = AsyncMock(return_value=existing)

        result = await repo.update(entry_id)
        assert result == existing
        repo.get_by_id.assert_called_once_with(entry_id)

    @pytest.mark.asyncio
    async def test_update_multiple_fields(self, repo):
        entry_id = uuid4()
        expected = {"id": str(entry_id), "title": "t", "description": "d"}
        repo.fetch_one = AsyncMock(return_value=expected)

        result = await repo.update(entry_id, title="t", description="d")
        assert result == expected


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_success(self, repo):
        repo.execute = AsyncMock(return_value="DELETE 1")
        result = await repo.delete(uuid4())
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_not_found(self, repo):
        repo.execute = AsyncMock(return_value="DELETE 0")
        result = await repo.delete(uuid4())
        assert result is False


class TestCountByUser:
    @pytest.mark.asyncio
    async def test_count_returns_number(self, repo):
        repo.fetch_one = AsyncMock(return_value={"count": 7})
        result = await repo.count_by_user("u1")
        assert result == 7

    @pytest.mark.asyncio
    async def test_count_returns_zero_when_none(self, repo):
        repo.fetch_one = AsyncMock(return_value=None)
        result = await repo.count_by_user("u1")
        assert result == 0
