"""
Tests for BaseRelationshipRepository — 30 uncovered lines.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.data_access.neo4j.relationships.base_relationship_repository import BaseRelationshipRepository


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute_read = AsyncMock(return_value=[])
    db.execute_write = AsyncMock(return_value={"relationships_deleted": 1})
    return db


@pytest.fixture
def repo(mock_db):
    return BaseRelationshipRepository(mock_db)


class TestGetRelationships:
    @pytest.mark.asyncio
    async def test_outgoing_direction(self, repo, mock_db):
        mock_db.execute_read = AsyncMock(return_value=[{"r": {}, "rel_type": "MENTIONS", "rel_id": 1}])
        results = await repo.get_relationships("n1", direction="OUTGOING")
        assert len(results) == 1
        query = mock_db.execute_read.call_args[0][0]
        assert "(n)-[r]->()" in query

    @pytest.mark.asyncio
    async def test_incoming_direction(self, repo, mock_db):
        await repo.get_relationships("n1", direction="INCOMING")
        query = mock_db.execute_read.call_args[0][0]
        assert "()<-[r]-(n)" in query

    @pytest.mark.asyncio
    async def test_both_direction(self, repo, mock_db):
        await repo.get_relationships("n1", direction="BOTH")
        query = mock_db.execute_read.call_args[0][0]
        assert "(n)-[r]-()" in query

    @pytest.mark.asyncio
    async def test_with_rel_type_filter(self, repo, mock_db):
        await repo.get_relationships("n1", rel_type="MENTIONS")
        params = mock_db.execute_read.call_args[0][1]
        assert params["rel_type"] == "MENTIONS"

    @pytest.mark.asyncio
    async def test_without_rel_type_filter(self, repo, mock_db):
        await repo.get_relationships("n1")
        params = mock_db.execute_read.call_args[0][1]
        assert "rel_type" not in params

    @pytest.mark.asyncio
    async def test_returns_empty_list(self, repo):
        results = await repo.get_relationships("n1")
        assert results == []


class TestDeleteRelationship:
    @pytest.mark.asyncio
    async def test_delete_returns_true_when_deleted(self, repo):
        result = await repo.delete_relationship(42)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(self, repo, mock_db):
        mock_db.execute_write = AsyncMock(return_value={"relationships_deleted": 0})
        result = await repo.delete_relationship(99)
        assert result is False


class TestCreateRelationship:
    @pytest.mark.asyncio
    async def test_create_relationship_returns_key(self, repo):
        result = await repo._create_relationship(
            from_id="e1", to_id="c1",
            from_label="Entry", to_label="Concept",
            rel_type="MENTIONS",
            properties={"weight": 0.9}
        )
        assert "e1" in result
        assert "MENTIONS" in result
        assert "c1" in result

    @pytest.mark.asyncio
    async def test_create_relationship_no_properties(self, repo):
        result = await repo._create_relationship(
            from_id="e1", to_id="c1",
            from_label="Entry", to_label="Concept",
            rel_type="RELATES_TO",
            properties={}
        )
        assert result == "e1_RELATES_TO_c1"

    @pytest.mark.asyncio
    async def test_create_relationship_calls_execute_write(self, repo, mock_db):
        await repo._create_relationship("e1", "c1", "Entry", "Concept", "MENTIONS", {"w": 1})
        mock_db.execute_write.assert_called_once()


class TestFindByRelationship:
    @pytest.mark.asyncio
    async def test_find_by_relationship_returns_results(self, repo, mock_db):
        mock_db.execute_read = AsyncMock(return_value=[{"s": {"id": "e1"}, "r": {}}])
        results = await repo._find_by_relationship(
            target_id="c1", target_label="Concept",
            rel_type="MENTIONS", source_label="Entry",
            user_id="u1", limit=5
        )
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_find_by_relationship_passes_params(self, repo, mock_db):
        await repo._find_by_relationship("c1", "Concept", "MENTIONS", "Entry", "u1", limit=3)
        params = mock_db.execute_read.call_args[0][1]
        assert params["target_id"] == "c1"
        assert params["user_id"] == "u1"
        assert params["limit"] == 3
