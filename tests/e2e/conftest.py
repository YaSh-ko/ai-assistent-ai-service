import pytest
import pytest_asyncio
import os
import json
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport

# Ensure clean environment for settings
if "GIGACHAT_CREDENTIALS" in os.environ:
    del os.environ["GIGACHAT_CREDENTIALS"]
if "GIGACHAT_CLIENT_ID" in os.environ:
    del os.environ["GIGACHAT_CLIENT_ID"]
if "GIGACHAT_CLIENT_SECRET" in os.environ:
    del os.environ["GIGACHAT_CLIENT_SECRET"]

from app.main import app
from tests.e2e.utils import cleanup_test_data

from app.factory.model_factory import ModelFactory
from app.factory.database_factory import DatabaseFactory


# ---------------------------------------------------------------------------
# Shared in-memory session storage (session-scoped so it persists across tests)
# ---------------------------------------------------------------------------

class MockRecord(dict):
    """Mock asyncpg Record that behaves like a dict."""
    pass


# Session-level storage shared by all pool instances
_session_storage: dict = {}


async def _mock_create_pool(*args, **kwargs):
    """Return a MockPool that delegates to _session_storage."""

    async def mock_fetchrow(query, *args):
        query_upper = query.upper()

        if "INSERT INTO CHAT_SESSIONS" in query_upper and "RETURNING" in query_upper:
            if len(args) >= 2:
                session_id = args[0]
                user_id = args[1]
                status = args[2] if len(args) > 2 else 'active'
                _session_storage[session_id] = MockRecord({
                    'session_id': session_id,
                    'user_id': user_id,
                    'status': status,
                    'history': [],
                    'context': {},
                    'metadata': {},
                    'created_at': '2026-02-11T22:22:00+00:00',
                    'updated_at': '2026-02-11T22:22:00+00:00',
                })
                return _session_storage[session_id]

        elif "UPDATE CHAT_SESSIONS" in query_upper and "HISTORY = HISTORY ||" in query_upper:
            if len(args) >= 2:
                message_array_json = args[0]
                session_id = args[1]
                if session_id in _session_storage:
                    try:
                        messages = json.loads(message_array_json)
                        _session_storage[session_id]['history'].extend(messages)
                    except Exception:
                        pass
                    return _session_storage[session_id]

        elif "UPDATE CHAT_SESSIONS" in query_upper and "STATUS =" in query_upper:
            session_id = args[-1]
            if session_id in _session_storage:
                if len(args) >= 2:
                    _session_storage[session_id]['status'] = args[0]
                return _session_storage[session_id]

        elif "SELECT * FROM CHAT_SESSIONS WHERE SESSION_ID" in query_upper:
            session_id = args[0]
            return _session_storage.get(session_id)

        elif "SELECT HISTORY FROM CHAT_SESSIONS WHERE SESSION_ID" in query_upper:
            session_id = args[0]
            if session_id in _session_storage:
                return MockRecord({'history': _session_storage[session_id]['history']})

        return None

    async def mock_fetch(query, *args):
        return []

    async def mock_execute(query, *args):
        return "SELECT 1"

    class MockConnection:
        async def fetchrow(self, query, *args):
            return await mock_fetchrow(query, *args)
        async def fetch(self, query, *args):
            return await mock_fetch(query, *args)
        async def execute(self, query, *args):
            return await mock_execute(query, *args)
        async def executemany(self, query, args_list):
            return None

    _conn = MockConnection()

    class MockAcquire:
        async def __aenter__(self):
            return _conn
        async def __aexit__(self, *args):
            pass

    class MockPool:
        async def close(self):
            pass
        async def terminate(self):
            pass
        async def fetchrow(self, query, *args):
            return await mock_fetchrow(query, *args)
        async def fetch(self, query, *args):
            return await mock_fetch(query, *args)
        async def execute(self, query, *args):
            return await mock_execute(query, *args)
        def acquire(self):
            return MockAcquire()

    return MockPool()


async def mock_process_user_message(self, session_id, user_question, user_id, thread_id=None):
    """Mock RAGChain.process_user_message returning a fixed non-empty stream."""
    async def fake_stream():
        chunk = MagicMock()
        chunk.content = "Mocked LLM response for testing."
        yield chunk

    return fake_stream(), {
        "reasoning_steps": [],
        "filtered_results": [],
        "complexity": "simple",
        "selected_model": "mock",
    }


# ---------------------------------------------------------------------------
# Session-scoped fixtures for ChromaDB and RAGChain mocks
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def mock_chroma_session():
    """Session-scoped ChromaDB mock."""
    import chromadb
    chroma_patch = patch('chromadb.HttpClient')
    mock_http = chroma_patch.start()
    try:
        local_client = chromadb.EphemeralClient()
    except AttributeError:
        local_client = chromadb.Client()
    mock_http.return_value = local_client

    rag_patch = patch(
        'app.chains.rag_chain.RAGChain.process_user_message',
        new=mock_process_user_message,
    )
    rag_patch.start()

    yield local_client

    rag_patch.stop()
    chroma_patch.stop()


# Keep legacy names for compatibility
@pytest.fixture(scope="session", autouse=True)
def mock_databases(mock_chroma_session):
    return mock_chroma_session


@pytest.fixture(scope="session", autouse=True)
def mock_chroma(mock_chroma_session):
    return mock_chroma_session


# ---------------------------------------------------------------------------
# Function-scoped fixture that overrides ci_env's asyncpg patch
# This runs AFTER ci_env (which uses monkeypatch) and re-patches with our
# proper MockPool so that pool.fetchrow / pool.close are awaitable.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def override_asyncpg_patch(monkeypatch):
    """Override the ci_env asyncpg patch with a proper async mock pool.
    Also mock get_rag_chain to avoid GigaChatEmbeddings credential requirement.
    Clears any stale app.dependency_overrides left by other test modules."""
    from app.main import app as _app
    from app.api.deps import get_session_manager as _get_session_manager, get_rag_chain as _get_rag_chain

    # Clear any stale dependency overrides from other test modules (e.g. test_chat.py)
    _app.dependency_overrides.clear()

    monkeypatch.setattr(
        "app.providers.databases.postgres_provider.asyncpg.create_pool",
        _mock_create_pool,
    )

    # Reset the session_manager singleton so it gets re-initialized with the mock pool
    monkeypatch.setattr("app.api.deps._session_manager", None)

    # Mock get_rag_chain so it returns a minimal RAGChain-like object
    # without requiring GigaChat credentials or Neo4j
    class _MockRAGChain:
        async def process_user_message(self, session_id, user_question, user_id, thread_id=None):
            return await mock_process_user_message(self, session_id, user_question, user_id, thread_id)

    _mock_rag_instance = _MockRAGChain()

    async def _mock_get_rag_chain():
        return _mock_rag_instance

    monkeypatch.setattr("app.api.deps._rag_chain", _mock_rag_instance)
    monkeypatch.setattr("app.api.v1.chat_controller.get_rag_chain", _mock_get_rag_chain)


# ---------------------------------------------------------------------------
# Client fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(mock_chroma_session):
    """AsyncClient instance for E2E tests."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


# ---------------------------------------------------------------------------
# Cleanup fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def cleanup():
    """Cleanup test data and singletons after each test."""
    yield
    test_user_id = "test_user_e2e"

    try:
        await cleanup_test_data(test_user_id)
    except Exception as e:
        print(f"Error during data cleanup: {e}")

    await ModelFactory.close_all()
    await DatabaseFactory.close_all()
