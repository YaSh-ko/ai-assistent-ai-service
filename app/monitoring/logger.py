"""
Модуль логирования для приложения.
Настраивает стандартную библиотеку logging для использования во всех компонентах.
"""

import logging
import sys
from typing import Optional
from functools import lru_cache


# Форматтер для логов
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class ModelRequestFilter(logging.Filter):
    """Фильтр для добавления контекста модели в логи."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, 'model_name'):
            record.model_name = 'N/A'
        if not hasattr(record, 'request_id'):
            record.request_id = 'N/A'
        return True


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None
) -> None:
    """
    Настройка логирования для приложения.
    
    Args:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)
        log_file: Путь к файлу логов (опционально)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Удаляем существующие handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    console_handler.addFilter(ModelRequestFilter())
    root_logger.addHandler(console_handler)
    
    # File handler (опционально)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        file_handler.addFilter(ModelRequestFilter())
        root_logger.addHandler(file_handler)


@lru_cache(maxsize=128)
def get_logger(name: str) -> logging.Logger:
    """
    Получение логгера по имени.
    
    Args:
        name: Имя логгера (обычно __name__)
        
    Returns:
        Настроенный логгер
    """
    return logging.getLogger(name)


class ModelLogger:
    """
    Специализированный логгер для операций с моделями.
    Логирует вызовы моделей, ошибки и переключения.
    """
    
    def __init__(self, model_name: str):
        self._logger = get_logger(f"models.{model_name}")
        self._model_name = model_name
    
    def log_request(
        self,
        prompt_length: int,
        params: dict,
        session_id: Optional[str] = None
    ) -> None:
        """Логирование запроса к модели."""
        self._logger.info(
            f"Request: prompt_len={prompt_length}, "
            f"temp={params.get('temperature', 'N/A')}, "
            f"max_tokens={params.get('max_tokens', 'N/A')}, "
            f"session_id={session_id or 'N/A'}"
        )
    
    def log_response(
        self,
        content_length: int,
        tokens_used: int,
        latency_ms: float,
        finish_reason: str
    ) -> None:
        """Логирование ответа от модели."""
        self._logger.info(
            f"Response: content_len={content_length}, "
            f"tokens={tokens_used}, "
            f"latency={latency_ms:.2f}ms, "
            f"finish_reason={finish_reason}"
        )
    
    def log_error(
        self,
        error: Exception,
        context: Optional[str] = None
    ) -> None:
        """Логирование ошибки."""
        msg = f"Error: {type(error).__name__}: {error}"
        if context:
            msg = f"{context} - {msg}"
        self._logger.error(msg, exc_info=True)
    
    def log_stream_start(self) -> None:
        """Логирование начала стриминга."""
        self._logger.debug("Stream started")
    
    def log_stream_end(
        self,
        total_content_length: int,
        latency_ms: float
    ) -> None:
        """Логирование завершения стриминга."""
        self._logger.info(
            f"Stream completed: content_len={total_content_length}, "
            f"latency={latency_ms:.2f}ms"
        )
    
    def log_model_switch(
        self,
        from_model: str,
        to_model: str,
        reason: str = "manual"
    ) -> None:
        """Логирование переключения модели."""
        self._logger.info(
            f"Model switch: {from_model} -> {to_model}, reason={reason}"
        )


# Инициализация базового логирования при импорте
setup_logging()


# Legacy class для обратной совместимости
class Logger:
    """Logger configuration. (Legacy - use get_logger() instead)"""
    pass
