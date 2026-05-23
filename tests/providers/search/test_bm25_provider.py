"""
Tests for BM25Provider — 49 uncovered lines.
"""
import math
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def db_provider():
    p = AsyncMock()
    p._ensure_connection = AsyncMock()
    p.pool = AsyncMock()
    return p


@pytest.fixture
def provider(db_provider):
    from app.providers.search.bm25_provider import BM25Provider
    return BM25Provider(db_provider)


def _setup_db(db_provider, N=5, avgdl=100.0, query_terms=None, df=1, docs=None):
    """Wire up the mock pool for a typical BM25 search flow."""
    if query_terms is None:
        query_terms = [{"lexeme": "jupiter"}]
    if docs is None:
        docs = [
            {
                "id": "1", "user_id": "u1", "event_date": None,
                "title": "Jupiter planet", "description": "big planet",
                "created_at": None, "updated_at": None,
                "doc_length": 20,
                "vec": "'jupiter':1 'planet':2",
            }
        ]

    db_provider.pool.fetchrow = AsyncMock(return_value={"n": N, "avgdl": avgdl})
    db_provider.pool.fetch = AsyncMock(side_effect=[query_terms, docs])
    db_provider.pool.fetchval = AsyncMock(return_value=df)


def _mock_lock():
    """Return an async context manager mock for _query_lock."""
    lock = MagicMock()
    lock.__aenter__ = AsyncMock(return_value=None)
    lock.__aexit__ = AsyncMock(return_value=False)
    return lock


class TestBM25Search:
    @pytest.mark.asyncio
    async def test_raises_without_user_id(self, provider):
        with pytest.raises(ValueError, match="user_id is required"):
            await provider.search("hello")

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_docs(self, db_provider, provider):
        db_provider.pool.fetchrow = AsyncMock(return_value={"n": 0, "avgdl": 0})
        db_provider.pool.fetch = AsyncMock(return_value=[])

        with patch("app.providers.databases.postgres_provider.PostgresProvider._query_lock", new=_mock_lock()), \
             patch("app.providers.search.bm25_provider.settings") as s:
            s.SEARCH_CONFIG = {"bm25_k1": 1.5, "bm25_b": 0.75}
            result = await provider.search("hello", user_id="u1")

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_query_terms(self, db_provider, provider):
        db_provider.pool.fetchrow = AsyncMock(return_value={"n": 5, "avgdl": 100.0})
        db_provider.pool.fetch = AsyncMock(return_value=[])  # no lexemes

        with patch("app.providers.databases.postgres_provider.PostgresProvider._query_lock", new=_mock_lock()), \
             patch("app.providers.search.bm25_provider.settings") as s:
            s.SEARCH_CONFIG = {"bm25_k1": 1.5, "bm25_b": 0.75}
            result = await provider.search("hello", user_id="u1")

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_scored_results(self, db_provider, provider):
        _setup_db(db_provider)

        with patch("app.providers.databases.postgres_provider.PostgresProvider._query_lock", new=_mock_lock()), \
             patch("app.providers.search.bm25_provider.settings") as s:
            s.SEARCH_CONFIG = {"bm25_k1": 1.5, "bm25_b": 0.75}
            results = await provider.search("jupiter", user_id="u1")

        assert len(results) == 1
        assert results[0]["bm25_score"] > 0

    @pytest.mark.asyncio
    async def test_user_id_from_filter(self, db_provider, provider):
        _setup_db(db_provider)

        with patch("app.providers.databases.postgres_provider.PostgresProvider._query_lock", new=_mock_lock()), \
             patch("app.providers.search.bm25_provider.settings") as s:
            s.SEARCH_CONFIG = {"bm25_k1": 1.5, "bm25_b": 0.75}
            results = await provider.search("jupiter", filter={"user_id": "u1"})

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_top_k_limits_results(self, db_provider, provider):
        docs = [
            {
                "id": str(i), "user_id": "u1", "event_date": None,
                "title": f"doc {i}", "description": "text",
                "created_at": None, "updated_at": None,
                "doc_length": 10,
                "vec": "'jupiter':1",
            }
            for i in range(5)
        ]
        db_provider.pool.fetchrow = AsyncMock(return_value={"n": 5, "avgdl": 10.0})
        db_provider.pool.fetch = AsyncMock(side_effect=[[{"lexeme": "jupiter"}], docs])
        db_provider.pool.fetchval = AsyncMock(return_value=1)

        with patch("app.providers.databases.postgres_provider.PostgresProvider._query_lock", new=_mock_lock()), \
             patch("app.providers.search.bm25_provider.settings") as s:
            s.SEARCH_CONFIG = {"bm25_k1": 1.5, "bm25_b": 0.75}
            results = await provider.search("jupiter", top_k=2, user_id="u1")

        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_zero_score_docs_excluded(self, db_provider, provider):
        # Doc with no matching terms gets score 0 and should be excluded
        docs = [
            {
                "id": "1", "user_id": "u1", "event_date": None,
                "title": "unrelated", "description": "nothing",
                "created_at": None, "updated_at": None,
                "doc_length": 10,
                "vec": "'unrelated':1",  # no 'jupiter' term
            }
        ]
        db_provider.pool.fetchrow = AsyncMock(return_value={"n": 1, "avgdl": 10.0})
        db_provider.pool.fetch = AsyncMock(side_effect=[[{"lexeme": "jupiter"}], docs])
        db_provider.pool.fetchval = AsyncMock(return_value=0)

        with patch("app.providers.databases.postgres_provider.PostgresProvider._query_lock", new=_mock_lock()), \
             patch("app.providers.search.bm25_provider.settings") as s:
            s.SEARCH_CONFIG = {"bm25_k1": 1.5, "bm25_b": 0.75}
            results = await provider.search("jupiter", user_id="u1")

        assert results == []
