"""
VLLM Provider - провайдер для локального vLLM сервера.
Использует OpenAI-совместимый API.
"""

import asyncio
import aiohttp
import json
import time
from typing import Any, AsyncGenerator, Dict, Optional

from app.interfaces.model_provider import (
    BaseModelProvider, 
    ModelConfig, 
    ModelResponse, 
    StreamChunk,
    ModelError,
    ModelUnavailableError,
    TimeoutError
)
from app.core.config import settings
from app.monitoring.logger import get_logger
from app.monitoring.metrics import ModelMetrics

logger = get_logger(__name__)


class VLLMProvider(BaseModelProvider):
    """
    Провайдер для локального vLLM сервера.
    Использует OpenAI-совместимый API.
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ):
        """
        Инициализация VLLM провайдера.
        
        Args:
            base_url: URL vLLM сервера (по умолчанию из настроек)
            model_name: Имя модели на сервере
            api_key: API ключ (если требуется)
            temperature: Температура генерации
            max_tokens: Максимальное количество токенов
        """
        self._base_url = base_url or settings.VLLM_API_URL or "http://localhost:8000/v1"
        self._api_key = api_key or getattr(settings, 'VLLM_API_KEY', None)
        
        # Получаем имя модели из настроек или используем дефолт
        model = model_name or getattr(settings, 'VLLM_MODEL_NAME', 'local-model')
        
        config = ModelConfig(
            model_name=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=0.9,
            timeout=60,  # Локальные модели могут быть медленнее
            retry_attempts=3
        )
        
        super().__init__(config)
        
        self._session: Optional[aiohttp.ClientSession] = None
        self._metrics = ModelMetrics()
        
        logger.info(f"VLLMProvider initialized with base_url: {self._base_url}")
    
    @property
    def name(self) -> str:
        return "vllm"
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение или создание HTTP сессии."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    def _build_headers(self) -> Dict[str, str]:
        """Построение заголовков запроса."""
        headers = {
            "Content-Type": "application/json"
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers
    
    def _build_messages(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None
    ) -> list:
        """Построение списка сообщений для API."""
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        return messages
    
    async def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs
    ) -> ModelResponse:
        """Генерация ответа от vLLM."""
        start_time = time.time()
        
        try:
            session = await self._get_session()
            
            payload = {
                "model": self._config.model_name,
                "messages": self._build_messages(prompt, system_prompt),
                "temperature": kwargs.get("temperature", self._config.temperature),
                "max_tokens": kwargs.get("max_tokens", self._config.max_tokens),
                "top_p": kwargs.get("top_p", self._config.top_p),
                "stream": False
            }
            
            url = f"{self._base_url}/chat/completions"
            
            logger.debug(f"VLLM request to {url} with model {self._config.model_name}")
            
            async with session.post(
                url,
                headers=self._build_headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self._config.timeout)
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"VLLM API error: {response.status} - {error_text}")
                    
                    if response.status == 503:
                        raise ModelUnavailableError(self.model_name, "Server unavailable")
                    
                    raise ModelError(
                        f"API error: {response.status} - {error_text}",
                        self.model_name
                    )
                
                result = await response.json()
            
            # Парсинг ответа (OpenAI формат)
            choice = result.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content", "")
            
            usage = result.get("usage", {})
            
            latency = self._measure_latency(start_time)
            
            # Запись метрик
            self._metrics.record_request(
                model_name=self.name,
                success=True,
                latency_ms=latency,
                tokens=usage.get("total_tokens", 0)
            )
            
            logger.info(
                f"VLLM response: {len(content)} chars, "
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
            
        except aiohttp.ClientConnectorError as e:
            self._metrics.record_request(
                model_name=self.name,
                success=False,
                latency_ms=self._measure_latency(start_time)
            )
            logger.error(f"VLLM connection error: {e}")
            raise ModelUnavailableError(
                self.model_name,
                f"Cannot connect to vLLM server at {self._base_url}: {e}"
            )
            
        except asyncio.TimeoutError:
            self._metrics.record_request(
                model_name=self.name,
                success=False,
                latency_ms=self._measure_latency(start_time)
            )
            raise TimeoutError(self.model_name, self._config.timeout)
            
        except (ModelUnavailableError, TimeoutError):
            raise
            
        except Exception as e:
            self._metrics.record_request(
                model_name=self.name,
                success=False,
                latency_ms=self._measure_latency(start_time)
            )
            logger.error(f"VLLM generate error: {e}")
            raise ModelError(str(e), self.model_name)
    
    async def stream(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[StreamChunk, None]:
        """Стриминг токенов от vLLM."""
        start_time = time.time()
        total_content = ""
        
        try:
            session = await self._get_session()
            
            payload = {
                "model": self._config.model_name,
                "messages": self._build_messages(prompt, system_prompt),
                "temperature": kwargs.get("temperature", self._config.temperature),
                "max_tokens": kwargs.get("max_tokens", self._config.max_tokens),
                "top_p": kwargs.get("top_p", self._config.top_p),
                "stream": True
            }
            
            url = f"{self._base_url}/chat/completions"
            
            logger.debug(f"VLLM stream request to {url}")
            
            async with session.post(
                url,
                headers=self._build_headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self._config.timeout * 2)
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise ModelError(
                        f"API error: {response.status} - {error_text}",
                        self.model_name
                    )
                
                # Парсинг SSE потока (OpenAI формат)
                async for line in response.content:
                    line = line.decode("utf-8").strip()
                    
                    if not line:
                        continue
                    
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        
                        if data == "[DONE]":
                            yield StreamChunk(
                                content="",
                                is_final=True,
                                model_name=self.name,
                                finish_reason="stop"
                            )
                            break
                        
                        try:
                            chunk_data = json.loads(data)
                            choices = chunk_data.get("choices", [])
                            
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                finish_reason = choices[0].get("finish_reason")
                                
                                if content:
                                    total_content += content
                                    yield StreamChunk(
                                        content=content,
                                        is_final=False,
                                        model_name=self.name
                                    )
                                
                                if finish_reason:
                                    yield StreamChunk(
                                        content="",
                                        is_final=True,
                                        model_name=self.name,
                                        finish_reason=finish_reason
                                    )
                                    break
                                    
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse SSE chunk: {data}")
                            continue
            
            # Запись метрик
            latency = self._measure_latency(start_time)
            self._metrics.record_request(
                model_name=self.name,
                success=True,
                latency_ms=latency,
                tokens=len(total_content) // 4
            )
            
            logger.info(f"VLLM stream completed: {len(total_content)} chars, {latency:.2f}ms")
            
        except aiohttp.ClientConnectorError as e:
            self._metrics.record_request(
                model_name=self.name,
                success=False,
                latency_ms=self._measure_latency(start_time)
            )
            raise ModelUnavailableError(
                self.model_name,
                f"Cannot connect to vLLM server: {e}"
            )
            
        except Exception as e:
            self._metrics.record_request(
                model_name=self.name,
                success=False,
                latency_ms=self._measure_latency(start_time)
            )
            logger.error(f"VLLM stream error: {e}")
            raise ModelError(str(e), self.model_name)
    
    async def is_available(self) -> bool:
        """Проверка доступности vLLM сервера."""
        try:
            session = await self._get_session()
            
            # Проверяем endpoint моделей
            url = f"{self._base_url}/models"
            
            async with session.get(
                url,
                headers=self._build_headers(),
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    logger.debug("VLLM server is available")
                    return True
                else:
                    logger.warning(f"VLLM availability check failed: {response.status}")
                    return False
                    
        except Exception as e:
            logger.warning(f"VLLM availability check failed: {e}")
            return False
    
    async def get_available_models(self) -> list:
        """Получение списка доступных моделей на сервере."""
        try:
            session = await self._get_session()
            url = f"{self._base_url}/models"
            
            async with session.get(
                url,
                headers=self._build_headers(),
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return [m.get("id") for m in result.get("data", [])]
                return []
        except Exception as e:
            logger.error(f"Failed to get VLLM models: {e}")
            return []
    
    async def close(self) -> None:
        """Закрытие HTTP сессии."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("VLLM session closed")
    
    def __del__(self):
        """Деструктор."""
        if hasattr(self, '_session') and self._session and not self._session.closed:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._session.close())
                else:
                    loop.run_until_complete(self._session.close())
            except Exception:
                pass
