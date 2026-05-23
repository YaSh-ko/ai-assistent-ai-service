"""
Tests for VLLMProvider — 125 uncovered lines, highest priority.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import aiohttp

from app.providers.models.vllm_provider import VLLMProvider
from app.interfaces.model_provider import (
    ModelError, ModelUnavailableError, TimeoutError
)


@pytest.fixture
def provider():
    with patch("app.providers.models.vllm_provider.ModelMetrics"):
        p = VLLMProvider(
            base_url="http://localhost:8000/v1",
            model_name="test-model",
            temperature=0.5,
            max_tokens=100,
        )
    return p


def _make_response(status: int, json_data=None, text_data: str = ""):
    """Build a mock aiohttp response context manager."""
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data or {})
    resp.text = AsyncMock(return_value=text_data)
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, resp


def _patch_session(provider, mock_session):
    """Patch _get_session so it returns mock_session directly, bypassing aiohttp."""
    provider._get_session = AsyncMock(return_value=mock_session)


class TestVLLMProviderInit:
    def test_name(self, provider):
        assert provider.name == "vllm"

    def test_default_base_url(self):
        with patch("app.providers.models.vllm_provider.ModelMetrics"), \
             patch("app.providers.models.vllm_provider.settings") as s:
            s.VLLM_API_URL = None
            p = VLLMProvider()
        assert "localhost:8000" in p._base_url

    def test_custom_api_key(self):
        with patch("app.providers.models.vllm_provider.ModelMetrics"):
            p = VLLMProvider(api_key="secret")
        assert p._api_key == "secret"


class TestBuildHeaders:
    def test_no_api_key(self, provider):
        provider._api_key = None
        headers = provider._build_headers()
        assert "Authorization" not in headers
        assert headers["Content-Type"] == "application/json"

    def test_with_api_key(self, provider):
        provider._api_key = "mykey"
        headers = provider._build_headers()
        assert headers["Authorization"] == "Bearer mykey"


class TestBuildMessages:
    def test_without_system_prompt(self, provider):
        msgs = provider._build_messages("hello")
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "hello"

    def test_with_system_prompt(self, provider):
        msgs = provider._build_messages("hello", system_prompt="be helpful")
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"


class TestGenerate:
    @pytest.mark.asyncio
    async def test_generate_success(self, provider):
        response_json = {
            "choices": [{"message": {"content": "Jupiter"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 10, "prompt_tokens": 5, "completion_tokens": 5},
        }
        cm, _ = _make_response(200, json_data=response_json)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=cm)
        _patch_session(provider, mock_session)

        result = await provider.generate("What is the 5th planet?")
        assert result.content == "Jupiter"
        assert result.tokens_used == 10

    @pytest.mark.asyncio
    async def test_generate_503_raises_unavailable(self, provider):
        cm, _ = _make_response(503, text_data="Service Unavailable")
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=cm)
        _patch_session(provider, mock_session)

        with pytest.raises(ModelUnavailableError):
            await provider.generate("hello")

    @pytest.mark.asyncio
    async def test_generate_non_200_raises_model_error(self, provider):
        cm, _ = _make_response(400, text_data="Bad Request")
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=cm)
        _patch_session(provider, mock_session)

        with pytest.raises(ModelError):
            await provider.generate("hello")

    @pytest.mark.asyncio
    async def test_generate_connection_error(self, provider):
        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=aiohttp.ClientConnectorError(
            MagicMock(), OSError("refused")
        ))
        _patch_session(provider, mock_session)

        with pytest.raises(ModelUnavailableError):
            await provider.generate("hello")

    @pytest.mark.asyncio
    async def test_generate_timeout(self, provider):
        import asyncio as _asyncio
        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=_asyncio.TimeoutError())
        _patch_session(provider, mock_session)

        with pytest.raises(TimeoutError):
            await provider.generate("hello")

    @pytest.mark.asyncio
    async def test_generate_generic_exception(self, provider):
        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=RuntimeError("boom"))
        _patch_session(provider, mock_session)

        with pytest.raises(ModelError):
            await provider.generate("hello")


class TestStream:
    def _sse_lines(self, chunks, done=True):
        """Build async line iterator from SSE chunks."""
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
    async def test_stream_yields_chunks(self, provider):
        chunk = {"choices": [{"delta": {"content": "Jup"}, "finish_reason": None}]}
        done_chunk = {"choices": [{"delta": {}, "finish_reason": "stop"}]}

        resp = AsyncMock()
        resp.status = 200
        resp.content = self._sse_lines([chunk, done_chunk], done=False)

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=resp)
        cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=cm)
        _patch_session(provider, mock_session)

        results = []
        async for sc in provider.stream("hello"):
            results.append(sc)

        contents = [r.content for r in results if r.content]
        assert "Jup" in contents

    @pytest.mark.asyncio
    async def test_stream_done_signal(self, provider):
        resp = AsyncMock()
        resp.status = 200
        resp.content = self._sse_lines([], done=True)

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=resp)
        cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=cm)
        _patch_session(provider, mock_session)

        results = []
        async for sc in provider.stream("hello"):
            results.append(sc)

        finals = [r for r in results if r.is_final]
        assert len(finals) >= 1

    @pytest.mark.asyncio
    async def test_stream_non_200_raises(self, provider):
        resp = AsyncMock()
        resp.status = 500
        resp.text = AsyncMock(return_value="error")

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=resp)
        cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=cm)
        _patch_session(provider, mock_session)

        with pytest.raises(ModelError):
            async for _ in provider.stream("hello"):
                pass

    @pytest.mark.asyncio
    async def test_stream_connection_error(self, provider):
        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=aiohttp.ClientConnectorError(
            MagicMock(), OSError("refused")
        ))
        _patch_session(provider, mock_session)

        with pytest.raises(ModelUnavailableError):
            async for _ in provider.stream("hello"):
                pass


class TestIsAvailable:
    @pytest.mark.asyncio
    async def test_available_true(self, provider):
        resp = AsyncMock()
        resp.status = 200
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=resp)
        cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=cm)
        _patch_session(provider, mock_session)

        assert await provider.is_available() is True

    @pytest.mark.asyncio
    async def test_available_false_on_error(self, provider):
        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=Exception("down"))
        _patch_session(provider, mock_session)

        assert await provider.is_available() is False

    @pytest.mark.asyncio
    async def test_available_false_non_200(self, provider):
        resp = AsyncMock()
        resp.status = 503
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=resp)
        cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=cm)
        _patch_session(provider, mock_session)

        assert await provider.is_available() is False


class TestGetAvailableModels:
    @pytest.mark.asyncio
    async def test_returns_model_ids(self, provider):
        resp = AsyncMock()
        resp.status = 200
        resp.json = AsyncMock(return_value={"data": [{"id": "model-a"}, {"id": "model-b"}]})
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=resp)
        cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=cm)
        _patch_session(provider, mock_session)

        models = await provider.get_available_models()
        assert models == ["model-a", "model-b"]

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self, provider):
        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=Exception("fail"))
        _patch_session(provider, mock_session)

        assert await provider.get_available_models() == []


class TestClose:
    @pytest.mark.asyncio
    async def test_close_session(self, provider):
        mock_session = AsyncMock()
        mock_session.closed = False
        provider._session = mock_session

        await provider.close()
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_no_session(self, provider):
        provider._session = None
        await provider.close()  # should not raise
