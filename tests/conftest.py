import pytest
import pytest_asyncio
import os
import sys
import builtins
from unittest.mock import AsyncMock, MagicMock
from typing import AsyncGenerator, TypeVar, Any

# НЕ ТРОГАЙТЕ ЭТО!!!
@pytest_asyncio.fixture
def T():
    return TypeVar('T')

def pytest_configure(config):
    """БЛОКИРУЕТ psycopg и app.database ДО ЛЮБЫХ ИМПОРТОВ"""
    
    original_import = builtins.__import__
    
    def mock_import(name, *args, **kwargs):
        if 'psycopg' in name.lower():
            mock_module = MagicMock()
            mock_module.__name__ = name
            sys.modules[name] = mock_module
            return mock_module
        
        if name == 'app.database':
            mock_db = MagicMock()
            mock_db.__name__ = 'app.database'
            mock_db.psycopg = MagicMock()
            mock_db.get_pool = lambda: MagicMock()
            mock_db.init_pool = lambda: None
            sys.modules['app.database'] = mock_db
            return mock_db
        
        return original_import(name, *args, **kwargs)
    
    builtins.__import__ = mock_import

@pytest_asyncio.fixture
async def db_pool() -> AsyncGenerator[MagicMock, None]:
    """Mock database pool - ВАШ КОД БЕЗ ИЗМЕНЕНИЙ"""
    pool = MagicMock()
    connection = AsyncMock()
    transaction = AsyncMock()
    
    cm = AsyncMock()
    pool.acquire.return_value = cm
    cm.__aenter__.return_value = connection
    cm.__aexit__.return_value = None
    
    tx_cm = AsyncMock()
    connection.transaction = MagicMock(return_value=tx_cm)
    tx_cm.start = AsyncMock()
    tx_cm.commit = AsyncMock()
    tx_cm.rollback = AsyncMock()
    tx_cm.__aenter__.return_value = connection
    tx_cm.__aexit__.return_value = None
    
    db_state = {"entries": {}, "sessions": {}, "test_table": {}}

    async def query_side_effect(query, *args):
        default_record = {
            "id": 1, "name": "Test", "count": 10, "user_id": "user_123",
            "thread_id": "thread_unique", "session_id": "session_789",
            "last_active_at": 1234567890, "title": "Встреча с инвестором",
            "description": "Обсудили финансирование $100k", "event_date": "2025-11-25"
        }
        record = default_record.copy()

        if "INSERT INTO gigachat_sessions" in query:
            rec = default_record.copy()
            rec.update({"user_id": args[0], "thread_id": args[1], "session_id": args[2], "id": "session_id_1"})
            db_state["sessions"][rec["id"]] = rec
            db_state["sessions"][args[1]] = rec
            return rec
            
        elif "SELECT * FROM gigachat_sessions" in query:
            if "WHERE id =" in query:
                return db_state["sessions"].get(args[0], default_record)
            elif "WHERE thread_id =" in query:
                return db_state["sessions"].get(args[0], default_record)
                
        elif "UPDATE gigachat_sessions" in query:
            if args[0] in db_state["sessions"]:
                import time
                db_state["sessions"][args[0]]["last_active_at"] = time.time() + 1000
                return db_state["sessions"][args[0]]
            return default_record

        elif "INSERT INTO entries" in query:
            rec = default_record.copy()
            rec.update({"user_id": args[0], "title": args[1], "description": args[2], "event_date": args[3], "id": "entry_id_1"})
            db_state["entries"][rec["id"]] = rec
            return rec

        elif "SELECT * FROM entries" in query:
            if "WHERE id =" in query:
                return db_state["entries"].get(args[0])

        elif "UPDATE entries" in query:
            id_val = args[-1]
            if id_val in db_state["entries"]:
                if len(args) == 2:
                     db_state["entries"][id_val]["description"] = args[0]
                return db_state["entries"][id_val]
            return default_record

        elif "DELETE FROM entries" in query:
            if args[0] in db_state["entries"]:
                del db_state["entries"][args[0]]
            return "DELETE 1"

        elif "INSERT INTO test_table" in query:
             rec = default_record.copy()
             rec.update({"id": args[0], "name": args[1]})
             db_state["test_table"][args[0]] = rec
             return rec
             
        elif "UPDATE test_table" in query:
             if args[1] in db_state["test_table"]:
                 db_state["test_table"][args[1]]["name"] = args[0]
             return "UPDATE 1"
             
        elif "SELECT * FROM test_table" in query:
             return db_state["test_table"].get(args[0], default_record)

        return record

    connection.fetchrow.side_effect = query_side_effect
    
    async def fetch_side_effect(query, *args):
        record = await query_side_effect(query, *args)
        return [record]
        
    connection.fetch.side_effect = fetch_side_effect
    connection.execute.side_effect = query_side_effect
    
    yield pool

@pytest_asyncio.fixture
async def chroma_client() -> AsyncGenerator[AsyncMock, None]:
    """Mock ChromaDB client."""
    client = AsyncMock()
    doc = {"id": "test_id", "page_content": "Test content", "metadata": {"entry_id": "test_id", "user_id": "user_123"}}
    client.similarity_search.return_value = [doc]
    client.get_by_filter.side_effect = [[doc], [doc], []]
    yield client

@pytest.fixture(autouse=True)
def ci_env(monkeypatch):
    """CI environment mocks."""
    def mock_db(*a, **kw):
        return MagicMock()

    async def async_mock_db(*a, **kw):
        return MagicMock()
    
    monkeypatch.setattr("app.providers.databases.postgres_provider.asyncpg.create_pool", async_mock_db)
    monkeypatch.setattr("sqlalchemy.create_engine", mock_db)
    
    monkeypatch.setenv("POSTGRES_HOST", "mock")
    monkeypatch.setenv("POSTGRES_PASSWORD", "mock")
    monkeypatch.setenv("POSTGRES_DB", "mock")
    monkeypatch.setenv("POSTGRES_USER", "mock")
