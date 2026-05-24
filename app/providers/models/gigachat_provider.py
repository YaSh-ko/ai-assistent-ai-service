"""
GigaChat Provider - универсальный провайдер для всех версий GigaChat.
Поддерживает версии: base, pro, max
"""

import asyncio
import aiohttp
import json
import random
import time
import uuid
from typing import Any, AsyncGenerator, Dict, Optional

from app.interfaces.model_provider import (
    BaseModelProvider,
    ModelConfig,
    ModelResponse,
    StreamChunk,
    ModelError,
    ModelUnavailableError,
    RateLimitError,
    TimeoutError,
    ModelVersion
)
from app.core.config import settings
from app.monitoring.logger import get_logger
from app.monitoring.metrics import ModelMetrics
from app.utils.rate_limiter import AdaptiveRateLimiter

logger = get_logger(__name__)

# Константы
_RETRY_DELAYS = [1.0, 2.0, 4.0, 8.0]  # секунды между попытками при 429
_CONTENT_TYPE_JSON = "application/json"
_MAX_RETRY_AFTER_SECONDS = 30
_MAX_ATTEMPTS = len(_RETRY_DELAYS) + 1
_SYSTEM_RANDOM = random.SystemRandom()


def _get_retry_delay(base_delay: float) -> float:
    """Добавляет jitter к задержке для избежания thundering herd."""
    return base_delay * (0.5 + _SYSTEM_RANDOM.random())


# Конфигурации для каждой версии GigaChat
GIGACHAT_CONFIGS = {
    ModelVersion.BASE: {
        "model": "GigaChat",
        "temperature": 0.3,
        "max_tokens": 1000,
    },
    ModelVersion.PRO: {
        "model": "GigaChat-Pro",
        "temperature": 0.7,
        "max_tokens": 1500,
    },
    ModelVersion.MAX: {
        "model": "GigaChat-Max",
        "temperature": 0.5,
        "max_tokens": 2000,
    }
}


class GigaChatProvider(BaseModelProvider):
    """
    Универсальный провайдер для GigaChat API.
    Поддерживает все версии: base, pro, max.
    """

    # GigaChat API endpoints
    AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    API_URL = "https://gigachat.devices.sberbank.ru/api/v1"

    def __init__(
        self,
        version: str = "base",
        credentials: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        scope: Optional[str] = None
    ):
        """
        Инициализация GigaChat провайдера.

        Args:
            version: Версия модели ("base", "pro", "max")
            credentials: Base64-encoded credentials (альтернатива client_id/secret)
            client_id: Client ID для OAuth
            client_secret: Client Secret для OAuth
            scope: OAuth scope (по умолчанию GIGACHAT_API_PERS)
        """
        try:
            self._version = ModelVersion(version.lower())
        except ValueError:
            raise ValueError(f"Unknown GigaChat version: {version}. Use 'base', 'pro', or 'max'")

        version_config = GIGACHAT_CONFIGS[self._version]

        config = ModelConfig(
            model_name=version_config["model"],
            temperature=version_config["temperature"],
            max_tokens=version_config["max_tokens"],
            top_p=0.9,
            timeout=30,
            retry_attempts=3
        )

        super().__init__(config)

        # Credentials - handle empty strings as None
        self._credentials = credentials or settings.GIGACHAT_CREDENTIALS or None
        if self._credentials == "":
            self._credentials = None
        self._client_id = client_id or settings.GIGACHAT_CLIENT_ID or None
        if self._client_id == "":
            self._client_id = None
        self._client_secret = client_secret or settings.GIGACHAT_CLIENT_SECRET or None
        if self._client_secret == "":
            self._client_secret = None
        self._scope = scope or settings.GIGACHAT_SCOPE or "GIGACHAT_API_PERS"

        # Token management
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

        # Session management
        self._session: Optional[aiohttp.ClientSession] = None

        # Metrics
        self._metrics = ModelMetrics()

        # Rate limiter для предотвращения thundering herd
        self._rate_limiter = AdaptiveRateLimiter(initial_delay=0.0, max_delay=10.0)

        logger.info(f"GigaChatProvider initialized with version: {self._version.value}")

    @property
    def name(self) -> str:
        return f"gigachat_{self._version.value}" if self._version != ModelVersion.BASE else "gigachat"

    def _get_session(self) -> aiohttp.ClientSession:
        """Получение или создание HTTP сессии."""
        if self._session is None or self._session.closed:
            from app.core.ssl_utils import get_gigachat_ssl_context

            ssl_context = get_gigachat_ssl_context()
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    def _build_auth_header(self) -> str:
        """Формирование Authorization заголовка для OAuth."""
        if self._credentials:
            return f"Basic {self._credentials.strip()}"
        if self._client_id and self._client_secret:
            import base64
            creds = f"{self._client_id}:{self._client_secret}"
            encoded = base64.b64encode(creds.encode()).decode()
            return f"Basic {encoded}"
        raise ModelError(
            "No credentials provided for GigaChat authentication",
            self.model_name,
            retry_possible=False
        )

    async def _ensure_token(self) -> str:
        """Получение или обновление access token."""
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        session = self._get_session()
        auth_header = self._build_auth_header()

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": _CONTENT_TYPE_JSON,
            "Authorization": auth_header,
            "RqUID": str(uuid.uuid4())
        }

        logger.error(f"GigaChat auth headers: {headers}")

        try:
            async with session.post(self.AUTH_URL, headers=headers, data={"scope": self._scope}) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"GigaChat auth failed: {response.status} - {error_text}")
                    raise ModelUnavailableError(
                        self.model_name,
                        f"Authentication failed: {response.status}"
                    )

                result = await response.json()
                self._access_token = result["access_token"]
                expires_at = result.get("expires_at", 0)
                # GigaChat returns expires_at as Unix timestamp in milliseconds
                if expires_at > 1e12:
                    self._token_expires_at = expires_at / 1000
                else:
                    self._token_expires_at = time.time() + (expires_at or 1800)

                logger.debug("GigaChat token obtained successfully")
                return self._access_token

        except aiohttp.ClientError as e:
            logger.error(f"GigaChat auth network error: {e}")
            raise ModelUnavailableError(self.model_name, f"Network error: {e}")

    def _build_messages(self, prompt: str, system_prompt: Optional[str] = None) -> list:
        """Построение списка сообщений для API."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _prepare_request_headers(self, token: str, session_id: Optional[str] = None) -> Dict[str, str]:
        """Подготовка заголовков для запроса."""
        headers = {
            "Content-Type": _CONTENT_TYPE_JSON,
            "Authorization": f"Bearer {token}"
        }
        if session_id:
            headers["X-Session-ID"] = session_id
        return headers

    def _prepare_request_payload(
        self,
        prompt: str,
        system_prompt: Optional[str],
        stream: bool,
        **kwargs
    ) -> Dict[str, Any]:
        """Подготовка payload для запроса."""
        return {
            "model": self._config.model_name,
            "messages": self._build_messages(prompt, system_prompt),
            "temperature": kwargs.get("temperature", self._config.temperature),
            "max_tokens": kwargs.get("max_tokens", self._config.max_tokens),
            "top_p": kwargs.get("top_p", self._config.top_p),
            "stream": stream
        }

    async def _handle_rate_limit_response(
        self,
        response: aiohttp.ClientResponse,
        attempt: int
    ) -> RateLimitError:
        """Обработка 429 ответа."""
        retry_after = response.headers.get("Retry-After")
        retry_after_int = int(retry_after) if retry_after else None

        self._rate_limiter.on_rate_limit(retry_after_int)

        if retry_after_int and attempt < len(_RETRY_DELAYS):
            custom_delay = min(retry_after_int, _MAX_RETRY_AFTER_SECONDS)
            logger.warning(f"Retry-After: {custom_delay}с")
            await asyncio.sleep(custom_delay)

        return RateLimitError(self.model_name, retry_after_int)

    def _parse_response(self, result: Dict[str, Any], start_time: float) -> ModelResponse:
        """Парсинг успешного ответа от API."""
        choice = result.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        usage = result.get("usage", {})
        latency = self._measure_latency(start_time)

        self._metrics.record_request(
            model_name=self.name,
            success=True,
            latency_ms=latency,
            tokens=usage.get("total_tokens", 0)
        )

        logger.info(
            f"GigaChat response: {len(content)} chars, "
            f"{usage.get('total_tokens', 0)} tokens, {latency:.2f}ms"
        )

        return ModelResponse(
            content=content,
            model_name=self.name,
            tokens_used=usage.get("total_tokens", 0),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_ms=latency,
            finish_reason=choice.get("finish_reason", "stop"),
            raw_response=result
        )

    async def _wait_for_circuit_breaker(self) -> None:
        """Ожидание при активном circuit breaker."""
        if self._rate_limiter.should_circuit_break():
            logger.warning("Circuit breaker активирован - слишком много 429 ошибок")
            await asyncio.sleep(5)

    def _record_failure_metrics(self, start_time: float) -> None:
        """Запись метрик при ошибке."""
        self._metrics.record_request(
            model_name=self.name,
            success=False,
            latency_ms=self._measure_latency(start_time)
        )

    async def _execute_generate_attempt(
        self,
        prompt: str,
        system_prompt: Optional[str],
        session_id: Optional[str],
        attempt: int,
        start_time: float,
        **kwargs
    ) -> ModelResponse:
        """Выполнение одной попытки generate запроса."""
        await self._rate_limiter.acquire()

        token = await self._ensure_token()
        session = self._get_session()

        headers = self._prepare_request_headers(token, session_id)
        payload = self._prepare_request_payload(prompt, system_prompt, False, **kwargs)
        url = f"{self.API_URL}/chat/completions"

        logger.debug(f"GigaChat request to {url} with model {self._config.model_name}")

        async with session.post(
            url,
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=self._config.timeout)
        ) as response:
            if response.status == 429:
                raise await self._handle_rate_limit_response(response, attempt)

            if response.status != 200:
                error_text = await response.text()
                logger.error(f"GigaChat API error: {response.status} - {error_text}")
                raise ModelError(
                    f"API error: {response.status} - {error_text}",
                    self.model_name
                )

            result = await response.json()

        self._rate_limiter.on_success()
        return self._parse_response(result, start_time)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs
    ) -> ModelResponse:
        """Генерация ответа от GigaChat с retry при 429."""
        start_time = time.time()
        last_exc = None

        await self._wait_for_circuit_breaker()

        for attempt in range(_MAX_ATTEMPTS):
            if attempt > 0:
                delay = _get_retry_delay(_RETRY_DELAYS[attempt - 1])
                logger.warning(
                    f"429 от GigaChat generate, попытка {attempt + 1}/{_MAX_ATTEMPTS}, "
                    f"жду {delay:.2f}с"
                )
                await asyncio.sleep(delay)

            try:
                return await self._execute_generate_attempt(
                    prompt, system_prompt, session_id, attempt, start_time, **kwargs
                )

            except RateLimitError as e:
                last_exc = e
                continue

            except (TimeoutError, ModelUnavailableError):
                self._record_failure_metrics(start_time)
                raise

            except asyncio.TimeoutError:
                self._record_failure_metrics(start_time)
                raise TimeoutError(self.model_name, self._config.timeout)

            except Exception as e:
                self._record_failure_metrics(start_time)
                logger.error(f"GigaChat generate error: {e}")
                raise ModelError(str(e), self.model_name)

        # Все попытки исчерпаны
        self._record_failure_metrics(start_time)
        if last_exc:
            raise last_exc
        raise ModelError("All retry attempts exhausted", self.model_name)

    def _process_sse_chunk(
        self,
        data: str,
        total_content: str
    ) -> tuple[Optional[StreamChunk], str]:
        """Обработка одного SSE chunk."""
        if data == "[DONE]":
            return StreamChunk(
                content="",
                is_final=True,
                model_name=self.name,
                finish_reason="stop"
            ), total_content

        try:
            chunk_data = json.loads(data)
            choices = chunk_data.get("choices", [])

            if choices:
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")

                if content:
                    total_content += content
                    return StreamChunk(
                        content=content,
                        is_final=False,
                        model_name=self.name
                    ), total_content
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse SSE chunk: {data}")

        return None, total_content

    async def _do_stream_request(
        self,
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Выполняет один streaming запрос.
        Бросает RateLimitError при 429, ModelError при других ошибках.
        Yields StreamChunk по мере получения данных.
        """
        session = self._get_session()

        async with session.post(
            url,
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=self._config.timeout * 2)
        ) as response:
            if response.status == 429:
                retry_after = response.headers.get("Retry-After")
                retry_after_int = int(retry_after) if retry_after else None
                self._rate_limiter.on_rate_limit(retry_after_int)
                raise RateLimitError(self.model_name, retry_after_int)

            if response.status != 200:
                error_text = await response.text()
                raise ModelError(
                    f"API error: {response.status} - {error_text}",
                    self.model_name
                )

            async for line in response.content:
                line_str = line.decode("utf-8").strip()
                if not line_str or not line_str.startswith("data:"):
                    continue

                data = line_str[5:].strip()
                chunk, _ = self._process_sse_chunk(data, "")
                if chunk:
                    yield chunk
                    if chunk.is_final:
                        break

    async def _run_stream_retry_loop(
        self,
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
    ) -> AsyncGenerator[StreamChunk, None]:
        """Retry-цикл для streaming запроса с обработкой 429."""
        last_exc: Optional[Exception] = None
        total_content = ""

        for attempt in range(_MAX_ATTEMPTS):
            if attempt > 0:
                delay = _get_retry_delay(_RETRY_DELAYS[attempt - 1])
                logger.warning(
                    f"429 от GigaChat stream, попытка {attempt + 1}/{_MAX_ATTEMPTS}, "
                    f"жду {delay:.2f}с"
                )
                await asyncio.sleep(delay)

            await self._rate_limiter.acquire()

            try:
                async for chunk in self._do_stream_request(url, headers, payload):
                    if chunk.content:
                        total_content += chunk.content
                    if not chunk.is_final:
                        yield chunk
                    else:
                        self._rate_limiter.on_success()

                # Успешно завершили — выходим из retry-цикла
                last_exc = None
                break

            except RateLimitError as e:
                last_exc = e
                continue

        if last_exc is not None:
            raise last_exc

        # Финальный chunk с накопленным контентом для метрик
        yield StreamChunk(content=total_content, is_final=True, model_name=self.name, finish_reason="_meta")

    def _record_stream_success(self, start_time: float, total_content: str) -> None:
        """Запись метрик успешного stream."""
        latency = self._measure_latency(start_time)
        self._metrics.record_request(
            model_name=self.name,
            success=True,
            latency_ms=latency,
            tokens=len(total_content) // 4
        )
        logger.info(f"GigaChat stream completed: {len(total_content)} chars, {latency:.2f}ms")

    async def stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[StreamChunk, None]:
        """Стриминг токенов от GigaChat."""
        start_time = time.time()

        await self._wait_for_circuit_breaker()

        try:
            token = await self._ensure_token()
            headers = self._prepare_request_headers(token, session_id)
            headers["Accept"] = "text/event-stream"

            payload = self._prepare_request_payload(prompt, system_prompt, True, **kwargs)
            url = f"{self.API_URL}/chat/completions"

            logger.debug(f"GigaChat stream request to {url}")

            total_content = ""
            async for chunk in self._run_stream_retry_loop(url, headers, payload):
                if chunk.finish_reason == "_meta":
                    total_content = chunk.content
                else:
                    yield chunk

            self._record_stream_success(start_time, total_content)

        except Exception as e:
            self._record_failure_metrics(start_time)
            logger.error(f"GigaChat stream error: {e}")
            raise ModelError(str(e), self.model_name)

    async def is_available(self) -> bool:
        """Проверка доступности GigaChat API."""
        try:
            await self._ensure_token()
            return True
        except Exception as e:
            logger.warning(f"GigaChat availability check failed: {e}")
            return False

    async def close(self) -> None:
        """Закрытие HTTP сессии."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("GigaChat session closed")

    def __del__(self):
        """Деструктор - закрытие сессии."""
        if not (hasattr(self, '_session') and self._session and not self._session.closed):
            return
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._session.close())
            else:
                loop.run_until_complete(self._session.close())
        except Exception:
            pass
