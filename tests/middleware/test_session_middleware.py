"""
Tests for SessionMiddleware — 19 uncovered lines.
"""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.middleware.session_middleware import SessionMiddleware


def _make_app():
    async def homepage(request: Request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", homepage)])
    app.add_middleware(SessionMiddleware)
    return app


class TestSessionMiddleware:
    def test_generates_session_id_when_missing(self):
        client = TestClient(_make_app(), raise_server_exceptions=True)
        response = client.get("/")
        assert response.status_code == 200
        session_id = response.headers.get("X-Session-ID")
        assert session_id is not None
        # Should be a valid UUID
        uuid.UUID(session_id)

    def test_passes_through_valid_session_id(self):
        valid_id = str(uuid.uuid4())
        client = TestClient(_make_app(), raise_server_exceptions=True)
        response = client.get("/", headers={"X-Session-ID": valid_id})
        assert response.headers["X-Session-ID"] == valid_id

    def test_replaces_invalid_session_id(self):
        client = TestClient(_make_app(), raise_server_exceptions=True)
        response = client.get("/", headers={"X-Session-ID": "not-a-uuid"})
        returned_id = response.headers["X-Session-ID"]
        # Should be a fresh valid UUID, not the invalid one
        assert returned_id != "not-a-uuid"
        uuid.UUID(returned_id)

    def test_response_always_has_session_id_header(self):
        client = TestClient(_make_app(), raise_server_exceptions=True)
        for _ in range(3):
            response = client.get("/")
            assert "X-Session-ID" in response.headers
