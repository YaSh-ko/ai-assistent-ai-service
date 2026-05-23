import importlib
import sys
import types
from unittest.mock import MagicMock

import pytest

class _FakeCursor:
    def __init__(self):
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query):
        self.executed.append(query)


class _FakeConn:
    def __init__(self):
        self.cursor_obj = _FakeCursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_obj


def test_setup_langgraph_tables_requires_database_url(monkeypatch):
    fake_postgres_module = types.ModuleType("langgraph.checkpoint.postgres")
    fake_postgres_module.PostgresSaver = MagicMock()
    monkeypatch.setitem(sys.modules, "langgraph.checkpoint.postgres", fake_postgres_module)
    module = importlib.import_module("app.setup_langgraph_tables")

    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValueError, match="DATABASE_URL environment variable not set"):
        module.setup_langgraph_tables()


def test_setup_langgraph_tables_creates_tables(monkeypatch):
    fake_postgres_module = types.ModuleType("langgraph.checkpoint.postgres")
    fake_postgres_module.PostgresSaver = MagicMock()
    monkeypatch.setitem(sys.modules, "langgraph.checkpoint.postgres", fake_postgres_module)
    module = importlib.import_module("app.setup_langgraph_tables")

    fake_conn = _FakeConn()
    connect_mock = MagicMock(return_value=fake_conn)
    saver_instance = MagicMock()
    saver_cls = MagicMock(return_value=saver_instance)

    monkeypatch.setenv("DATABASE_URL", "postgres://test")
    monkeypatch.setattr(module.Connection, "connect", connect_mock)
    monkeypatch.setattr(module, "PostgresSaver", saver_cls)

    module.setup_langgraph_tables()

    connect_mock.assert_called_once_with("postgres://test", autocommit=True)
    saver_cls.assert_called_once_with(fake_conn)
    saver_instance.setup.assert_called_once()
    assert any("CREATE TABLE IF NOT EXISTS conversations" in q for q in fake_conn.cursor_obj.executed)
    assert any("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS states" in q for q in fake_conn.cursor_obj.executed)

