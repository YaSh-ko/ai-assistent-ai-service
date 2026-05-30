"""
Tests for LLMService — 27 uncovered lines.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm_service import LLMService
from app.interfaces.model_provider import ModelResponse, StreamChunk, ModelError


def _mock_response(content="answer", tokens=10):
    return ModelResponse(
        content=content,
        model_name="test",
        tokens_used=tokens,
        prompt_tokens=5,
        completion_tokens=5,
        latency_ms=50.0,
        finish_reason="stop",
    )


@pytest.fixture
def service():
    with patch("app.services.llm_service.ModelMetrics"), \
         patch("app.services.llm_service.ContextService") as MockCtx:
        ctx = MagicMock()
        ctx.format_context = MagicMock(return_value="[context]")
        MockCtx.return_value = ctx
        svc = LLMService()
    return svc


class TestGenerateResponse:
    @pytest.mark.asyncio
    async def test_generate_response_success(self, service):
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=_mock_response("Jupiter"))

        with patch("app.services.llm_service.ModelFactory") as MockFactory:
            MockFactory.get_model.return_value = mock_provider
            result = await service.generate_response("What is the 5th planet?")

        assert result.content == "Jupiter"

    @pytest.mark.asyncio
    async def test_generate_response_raises_model_error(self, service):
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(side_effect=ModelError("fail", "test"))

        with patch("app.services.llm_service.ModelFactory") as MockFactory:
            MockFactory.get_model.return_value = mock_provider
            with pytest.raises(ModelError):
                await service.generate_response("hello")


class TestStreamResponse:
    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self, service):
        chunks = [StreamChunk(content="Jup", is_final=False, model_name="test"),
                  StreamChunk(content="iter", is_final=True, model_name="test")]

        async def _gen(*args, **kwargs):
            for c in chunks:
                yield c

        mock_provider = MagicMock()
        mock_provider.stream = _gen

        with patch("app.services.llm_service.ModelFactory") as MockFactory:
            MockFactory.get_model.return_value = mock_provider
            results = []
            async for chunk in service.stream_response("hello"):
                results.append(chunk)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_stream_raises_model_error(self, service):
        async def _err(*args, **kwargs):
            raise ModelError("fail", "test")
            yield  # make it a generator

        mock_provider = MagicMock()
        mock_provider.stream = _err

        with patch("app.services.llm_service.ModelFactory") as MockFactory:
            MockFactory.get_model.return_value = mock_provider
            with pytest.raises(ModelError):
                async for _ in service.stream_response("hello"):
                    pass


class TestAutoSelectAndGenerate:
    @pytest.mark.asyncio
    async def test_auto_select_calls_model_selector(self, service):
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=_mock_response("ok"))

        with patch("app.services.llm_service.ModelSelector") as MockSelector:
            MockSelector.get_model.return_value = mock_provider
            result = await service.auto_select_and_generate("hello", query_type="simple_question")

        assert result.content == "ok"
        MockSelector.get_model.assert_called_once_with("simple_question")


class TestGenerateWithFallback:
    @pytest.mark.asyncio
    async def test_fallback_generates_response(self, service):
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=_mock_response("fallback answer"))

        with patch("app.services.llm_service.ModelFactory") as MockFactory:
            MockFactory.get_model_with_fallback = AsyncMock(return_value=mock_provider)
            result = await service.generate_with_fallback("hello")

        assert result.content == "fallback answer"


class TestGenerateWithContext:
    @pytest.mark.asyncio
    async def test_prepends_context_to_prompt(self, service):
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=_mock_response("ctx answer"))

        with patch("app.services.llm_service.ModelFactory") as MockFactory:
            MockFactory.get_model.return_value = mock_provider
            result = await service.generate_with_context(
                "hello", context_messages=[{"role": "user", "content": "hi"}]
            )

        assert result.content == "ctx answer"
        call_args = mock_provider.generate.call_args
        assert "[context]" in call_args.kwargs.get("prompt", call_args.args[0] if call_args.args else "")


class TestModelManagement:
    def test_get_current_model(self, service):
        with patch("app.services.llm_service.ModelFactory") as MockFactory:
            MockFactory.get_current_model.return_value = "gpt"
            assert service.get_current_model() == "gpt"

    def test_set_current_model(self, service):
        with patch("app.services.llm_service.ModelFactory") as MockFactory:
            service.set_current_model("claude")
            MockFactory.set_current_model.assert_called_once_with("claude")

    def test_get_available_models(self, service):
        with patch("app.services.llm_service.ModelFactory") as MockFactory:
            MockFactory.get_available_models.return_value = ["gpt", "claude"]
            assert service.get_available_models() == ["gpt", "claude"]

    @pytest.mark.asyncio
    async def test_check_models_availability(self, service):
        with patch("app.services.llm_service.ModelFactory") as MockFactory:
            MockFactory.check_availability = AsyncMock(return_value={"gpt": True})
            result = await service.check_models_availability()
            assert result == {"gpt": True}

    def test_get_metrics(self, service):
        service._metrics = MagicMock()
        service._metrics.get_all_stats.return_value = {"gpt": {}}
        assert service.get_metrics() == {"gpt": {}}


class TestLegacyGenerate:
    @pytest.mark.asyncio
    async def test_legacy_generate_returns_string(self, service):
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=_mock_response("text answer"))

        with patch("app.services.llm_service.ModelSelector") as MockSelector:
            MockSelector.get_model.return_value = mock_provider
            result = await service.generate("hello")

        assert result == "text answer"
