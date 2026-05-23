"""
Tests for app/api/runs.py — 26 uncovered lines.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api.runs import router, _format_sse, _extract_text_content, _extract_user_message


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_app(rag_chain=None):
    app = FastAPI()
    if rag_chain is None:
        rag_chain = AsyncMock()
        rag_chain.process_user_message = AsyncMock(return_value=(iter([]), None))

    async def _get_rag():
        return rag_chain

    from app.api.deps import get_rag_chain
    app.dependency_overrides[get_rag_chain] = _get_rag
    app.include_router(router)
    return app


# ── unit tests ────────────────────────────────────────────────────────────────

class TestFormatSSE:
    def test_format_sse_basic(self):
        result = _format_sse("metadata", {"run_id": "123"})
        assert result.startswith("event: metadata\n")
        assert '"run_id": "123"' in result
        assert result.endswith("\n\n")


class TestExtractTextContent:
    def test_string_content(self):
        assert _extract_text_content("hello") == "hello"

    def test_list_of_strings(self):
        assert _extract_text_content(["hello", " world"]) == "hello  world"

    def test_list_of_blocks(self):
        blocks = [{"type": "text", "text": "hi"}, {"type": "text", "text": "there"}]
        assert _extract_text_content(blocks) == "hi there"

    def test_empty_list(self):
        assert _extract_text_content([]) == ""

    def test_none_returns_empty(self):
        assert _extract_text_content(None) == ""


class TestExtractUserMessage:
    def test_extracts_last_human_message(self):
        input_data = {
            "messages": [
                {"type": "human", "content": "first"},
                {"type": "ai", "content": "response"},
                {"type": "human", "content": "second"},
            ]
        }
        assert _extract_user_message(input_data) == "second"

    def test_no_messages_returns_none(self):
        assert _extract_user_message({"messages": []}) is None

    def test_none_input_returns_none(self):
        assert _extract_user_message(None) is None

    def test_no_human_message_returns_none(self):
        input_data = {"messages": [{"type": "ai", "content": "hi"}]}
        assert _extract_user_message(input_data) is None


# ── integration tests ─────────────────────────────────────────────────────────

class TestStreamRunCreate:
    def test_empty_input_returns_empty_state(self):
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.post("/threads/t1/runs/stream", json={})
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    def test_stream_with_user_message(self):
        async def _stream():
            chunk = MagicMock()
            chunk.content = "Jupiter"
            yield chunk

        rag_chain = AsyncMock()
        rag_chain.process_user_message = AsyncMock(return_value=(_stream(), None))

        app = _make_app(rag_chain)
        client = TestClient(app, raise_server_exceptions=True)

        payload = {
            "input": {
                "messages": [{"type": "human", "content": "What is the 5th planet?"}]
            }
        }
        resp = client.post("/threads/t1/runs/stream", json=payload)
        assert resp.status_code == 200
        body = resp.text
        assert "metadata" in body
        assert "values" in body

    def test_stream_error_yields_error_event(self):
        rag_chain = AsyncMock()
        rag_chain.process_user_message = AsyncMock(side_effect=RuntimeError("boom"))

        app = _make_app(rag_chain)
        client = TestClient(app, raise_server_exceptions=False)

        payload = {
            "input": {
                "messages": [{"type": "human", "content": "hello"}]
            }
        }
        resp = client.post("/threads/t1/runs/stream", json=payload)
        assert resp.status_code == 200
        assert "error" in resp.text


class TestOtherEndpoints:
    def test_get_runs_returns_empty_list(self):
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/threads/t1/runs/")
        assert resp.status_code == 200
        assert resp.json() == []
