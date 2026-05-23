"""
Tests for add_cors_middleware.
"""
import pytest
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.middleware.cors_middleware import add_cors_middleware


def _make_app():
    async def homepage(request: Request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", homepage)])
    add_cors_middleware(app)
    return app


class TestCorsMiddleware:
    def test_cors_headers_on_preflight(self):
        client = TestClient(_make_app(), raise_server_exceptions=True)
        response = client.options(
            "/",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") in ("*", "http://example.com")

    def test_cors_header_on_get(self):
        client = TestClient(_make_app(), raise_server_exceptions=True)
        response = client.get("/", headers={"Origin": "http://example.com"})
        assert "access-control-allow-origin" in response.headers

    def test_expose_session_id_header(self):
        client = TestClient(_make_app(), raise_server_exceptions=True)
        response = client.get("/", headers={"Origin": "http://example.com"})
        expose = response.headers.get("access-control-expose-headers", "")
        assert "X-Session-ID" in expose
