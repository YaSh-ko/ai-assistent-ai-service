"""
Tests for AuthMiddleware.
"""
import pytest
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.middleware.auth_middleware import AuthMiddleware


def _make_app():
    async def homepage(request: Request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", homepage, methods=["GET", "POST"])])
    app.add_middleware(AuthMiddleware)
    return app


class TestAuthMiddleware:
    def test_passes_request_through(self):
        client = TestClient(_make_app(), raise_server_exceptions=True)
        response = client.get("/")
        assert response.status_code == 200
        assert response.text == "ok"

    def test_post_request_passes_through(self):
        client = TestClient(_make_app(), raise_server_exceptions=True)
        response = client.post("/")
        assert response.status_code == 200
