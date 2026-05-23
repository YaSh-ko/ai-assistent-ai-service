"""
Tests for GigaChatProvider — 112 uncovered lines.
"""
import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.providers.models.gigachat_provider import GigaChatProvider
from app.interfaces.model_provider import (
    ModelError, ModelUnavailableError, RateLimitError, TimeoutError
)


def _make_provider(**kwargs):
    with patch("app.providers.models.gigachat_provider.ModelMetrics"), \
         patch("app.providers.models.gigachat_provider.settings") as s:
        s.GIGACHAT_CREDENTIALS = "dGVzdA=="
        s.GIGACHAT_CLIENT_ID = None
        s.GIGACHAT_CLIENT_SECRET = None
        s.GIGACHAT_SCOPE = "GIGACHAT_API_PERS"
        p = GigaChatProvider(**kwargs)
    return p


def _patch_session(provider, mock_session):
    provider._get_session = MagicMock(return_value=mock_session)


def _patch_token(provider, token="fake-token"):
    provider._ensure_token = AsyncMock(return_value=token)


def _make_cm(status, json_data=None, text_data="", headers=None):
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data or {})
    resp.text = AsyncMock(return_value=text_data)
    resp.headers = headers or {}
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, resp


class TestInit:
    def test_base_version_name(self):
        p = _make_provider()
        assert p.name == "gigachat"

    def test_pro_version_name(self):
        p = _make_provider(version="pro")
        assert p.name == "gigachat_pro"

    def test_max_version_name(self):
        p = _make_provider(version="max")
        assert p.name == "gigachat_max"

    def test_invalid_version_raises(self):
        with pytest.raises(ValueError, match="Unknown GigaChat version"):
            _make_provider(version="ultra")

    def test_credentials_from_arg(self):
        p = _make_provider(credentials="mycreds")
        assert p._credentials == "mycreds"


class TestEnsureToken:
    @pytest.mark.asyncio
    async def test_returns_cached_token(self):
        p = _make_provider()
        p._access_token = "cached"
        p._token_expires_at = time.time() + 3600
        token = await p._ensure_token()
        assert token == "cached"

    @pytest.mark.asyncio
    async def test_fetches_new_token(self):
        p = _make_provider()
        p._access_token = None

        auth_resp = {"access_token": "new-token", "expires_at": int(time.time() * 1000) + 1_800_000}
        cm, _ = _make_cm(200, json_data=auth_resp)
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=cm)
        _patch_session(p, mock_session)

        token = await p._ensure_token()
        assert token == "new-token"

    @pytest.mark.asyncio
    async def test_auth_failure_raises_unavailable(self):
        p = _make_provider()
        p._access_token = None

        cm, _ = _make_cm(401, text_data="Unauthorized")
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=cm)
        _patch_session(p, mock_session)

        with pytest.raises(ModelUnavailableError):
            await p._ensure_token()

    @pytest.mark.asyncio
    async def test_no_credentials_raises_model_error(self):
        with patch("app.providers.models.gigachat_provider.ModelMetrics"), \
             patch("app.providers.models.gigachat_provider.settings") as s:
            s.GIGACHAT_CREDENTIALS = None
            s.GIGACHAT_CLIENT_ID = None
            s.GIGACHAT_CLIENT_SECRET = None
            s.GIGACHAT_SCOPE = "GIGACHAT_API_PERS"
            p = GigaChatProvider()

        p._access_token = None
        mock_session = MagicMock()
        _patch_session(p, mock_session)

        with pytest.raises(ModelError, match="No credentials"):
            await p._ensure_token()

    @pytest.mark.asyncio
    async def test_client_id_secret_builds_basic_auth(self):
        with patch("app.providers.models.gigachat_provider.ModelMetrics"), \
             patch("app.providers.models.gigachat_provider.settings") as s:
            s.GIGACHAT_CREDENTIALS = None
            s.GIGACHAT_CLIENT_ID = "cid"
            s.GIGACHAT_CLIENT_SECRET = "csecret"
            s.GIGACHAT_SCOPE = "GIGACHAT_API_PERS"
            p = GigaChatProvider()

        p._access_token = None
        auth_resp = {"access_token": "tok", "expires_at": int(time.time() * 1000) + 1_800_000}
        cm, _ = _make_cm(200, json_data=auth_resp)
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=cm)
        _patch_session(p, mock_session)

        token = await p._ensure_token()
        assert token == "tok"


class TestGenerate:
    @pytest.mark.asyncio
    async def test_generate_success(self):
        p = _make_provider()
        _patch_token(p)

        resp_json = {
            "choices": [{"message": {"content": "Jupiter"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 20, "prompt_tokens": 10, "completion_tokens": 10},
        }
        cm, _ = _make_cm(200, json_data=resp_json)
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=cm)
        _patch_session(p, mock_session)

        result = await p.generate("What is the 5th planet?")
        assert result.content == "Jupiter"
        assert result.tokens_used == 20

    @pytest.mark.asyncio
    async def test_generate_429_raises_rate_limit(self):
        p = _make_provider()
        _patch_token(p)

        cm, resp = _make_cm(429, headers={"Retry-After": "5"})
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=cm)
        _patch_session(p, mock_session)

        with patch("app.providers.models.gigachat_provider.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RateLimitError):
                await p.generate("hello")

    @pytest.mark.asyncio
    async def test_generate_non_200_raises_model_error(self):
        p = _make_provider()
        _patch_token(p)

        cm, _ = _make_cm(500, text_data="Server Error")
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=cm)
        _patch_session(p, mock_session)

        with pytest.raises(ModelError):
            await p.generate("hello")

    @pytest.mark.asyncio
    async def test_generate_timeout(self):
        import asyncio as _asyncio
        p = _make_provider()
        _patch_token(p)

        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=_asyncio.TimeoutError())
        _patch_session(p, mock_session)

        with pytest.raises(TimeoutError):
            await p.generate("hello")

    @pytest.mark.asyncio
    async def test_generate_with_session_id(self):
        p = _make_provider()
        _patch_token(p)

        resp_json = {
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 5, "prompt_tokens": 3, "completion_tokens": 2},
        }
        cm, _ = _make_cm(200, json_data=resp_json)
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=cm)
        _patch_session(p, mock_session)

        result = await p.generate("hello", session_id="sess-123")
        assert result.content == "ok"


class TestStream:
    def _sse_lines(self, chunks, done=True):
        lines = []
        for c in chunks:
            lines.append(f"data: {json.dumps(c)}\n".encode())
        if done:
            lines.append(b"data: [DONE]\n")

        async def _iter():
            for line in lines:
                yield line

        return _iter()

    @pytest.mark.asyncio
    async def test_stream_yields_content(self):
        p = _make_provider()
        _patch_token(p)

        chunk = {"choices": [{"delta": {"content": "Jup"}}]}
        resp = AsyncMock()
        resp.status = 200
        resp.content = self._sse_lines([chunk], done=True)

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=resp)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=cm)
        _patch_session(p, mock_session)

        results = []
        async for sc in p.stream("hello"):
            results.append(sc)

        contents = [r.content for r in results if r.content]
        assert "Jup" in contents

    @pytest.mark.asyncio
    async def test_stream_non_200_raises(self):
        p = _make_provider()
        _patch_token(p)

        resp = AsyncMock()
        resp.status = 500
        resp.text = AsyncMock(return_value="error")
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=resp)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=cm)
        _patch_session(p, mock_session)

        with pytest.raises(ModelError):
            async for _ in p.stream("hello"):
                pass

    @pytest.mark.asyncio
    async def test_stream_retries_on_429_then_succeeds(self):
        """429 на первой попытке → retry → успех."""
        p = _make_provider()
        _patch_token(p)

        # Первый ответ — 429
        resp_429 = AsyncMock()
        resp_429.status = 429
        resp_429.headers = {}
        cm_429 = AsyncMock()
        cm_429.__aenter__ = AsyncMock(return_value=resp_429)
        cm_429.__aexit__ = AsyncMock(return_value=False)

        # Второй ответ — успешный стрим
        chunk = {"choices": [{"delta": {"content": "Hello"}}]}

        async def _sse():
            yield f"data: {json.dumps(chunk)}\n".encode()
            yield b"data: [DONE]\n"

        resp_ok = AsyncMock()
        resp_ok.status = 200
        resp_ok.content = _sse()
        cm_ok = AsyncMock()
        cm_ok.__aenter__ = AsyncMock(return_value=resp_ok)
        cm_ok.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=[cm_429, cm_ok])
        _patch_session(p, mock_session)

        # Патчим sleep чтобы тест не ждал
        with patch("app.providers.models.gigachat_provider.asyncio.sleep", new_callable=AsyncMock):
            results = []
            async for sc in p.stream("hello"):
                results.append(sc)

        contents = [r.content for r in results if r.content]
        assert "Hello" in contents
        assert mock_session.post.call_count == 2

    @pytest.mark.asyncio
    async def test_stream_all_attempts_429_raises(self):
        """Все попытки возвращают 429 → RateLimitError."""
        p = _make_provider()
        _patch_token(p)

        resp_429 = AsyncMock()
        resp_429.status = 429
        resp_429.headers = {}
        cm_429 = AsyncMock()
        cm_429.__aenter__ = AsyncMock(return_value=resp_429)
        cm_429.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        # 5 попыток (_MAX_ATTEMPTS = 5)
        mock_session.post = MagicMock(return_value=cm_429)
        _patch_session(p, mock_session)

        with patch("app.providers.models.gigachat_provider.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises((RateLimitError, ModelError)):
                async for _ in p.stream("hello"):
                    pass


class TestIsAvailable:
    @pytest.mark.asyncio
    async def test_available_when_token_ok(self):
        p = _make_provider()
        p._ensure_token = AsyncMock(return_value="tok")
        assert await p.is_available() is True

    @pytest.mark.asyncio
    async def test_unavailable_on_exception(self):
        p = _make_provider()
        p._ensure_token = AsyncMock(side_effect=Exception("auth failed"))
        assert await p.is_available() is False


class TestClose:
    @pytest.mark.asyncio
    async def test_close_open_session(self):
        p = _make_provider()
        mock_session = AsyncMock()
        mock_session.closed = False
        p._session = mock_session
        await p.close()
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_no_session(self):
        p = _make_provider()
        p._session = None
        await p.close()  # should not raise
