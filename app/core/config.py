"""
Конфигурация приложения.
Загружает настройки из переменных окружения и .env файла.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Get project root to locate .env
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOTENV_PATH = PROJECT_ROOT / ".env"
DOTENV_LOCAL_PATH = PROJECT_ROOT / ".env.local"

# Use .env.local if it exists (local dev overrides Docker hostnames)
_env_files = [str(DOTENV_PATH)]
if DOTENV_LOCAL_PATH.exists():
    _env_files.append(str(DOTENV_LOCAL_PATH))


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Python AI Service"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    ROOT_PATH: str = "/ai"

    # =================================
    # MODEL SETTINGS
    # =================================
    
    # Текущая модель по умолчанию
    CURRENT_MODEL: str = "gigachat"
    
    # Маппинг типов задач на модели
    TASK_MODEL_MAP: Dict[str, str] = {
        "simple_question": "gigachat",
        "dialogue": "gigachat",
        "analysis": "gigachat_pro",
        "complex": "gigachat_max",
    }
    
    # Маппинг сложности запросов на модели GigaChat
    MODEL_COMPLEXITY_MAP: Dict[str, str] = {
        "simple": "gigachat",
        "medium": "gigachat_pro",
        "complex": "gigachat_max",
    }

    
    # GigaChat Base Configuration
    GIGACHAT_BASE_CONFIG: Dict[str, Any] = {
        "model": "GigaChat",
        "temperature": float(os.getenv("GIGACHAT_TEMPERATURE", "0.3")),
        "max_tokens": int(os.getenv("GIGACHAT_MAX_TOKENS", "1000")),
        "top_p": 0.9,
        "timeout": 30,
        "retry_attempts": 3,
    }
    
    # GigaChat Pro Configuration
    GIGACHAT_PRO_CONFIG: Dict[str, Any] = {
        "model": "GigaChat-Pro",
        "temperature": float(os.getenv("GIGACHAT_PRO_TEMPERATURE", "0.7")),
        "max_tokens": int(os.getenv("GIGACHAT_PRO_MAX_TOKENS", "1500")),
        "top_p": 0.9,
        "timeout": 30,
        "retry_attempts": 3,
    }
    
    # GigaChat Max Configuration
    GIGACHAT_MAX_CONFIG: Dict[str, Any] = {
        "model": "GigaChat-Max",
        "temperature": float(os.getenv("GIGACHAT_MAX_TEMPERATURE", "0.5")),
        "max_tokens": int(os.getenv("GIGACHAT_MAX_MAX_TOKENS", "2000")),
        "top_p": 0.9,
        "timeout": 45,
        "retry_attempts": 3,
    }

    # =================================
    # SEARCH CONFIG
    # =================================
    SEARCH_CONFIG: Dict[str, Any] = {
        "search_type": os.getenv("SEARCH_TYPE", "hybrid"),
        "hybrid_search_k": int(os.getenv("TOP_K_RESULTS", "10")),
        "reranker_top_n": 5,
        "bm25_weight": float(os.getenv("HYBRID_BM25_WEIGHT", "0.5")),
        "vector_weight": float(os.getenv("HYBRID_VECTOR_WEIGHT", "0.5")),
        "bm25_k1": float(os.getenv("BM25_K1", "1.5")),
        "bm25_b": float(os.getenv("BM25_B", "0.75")),
        "similarity_threshold": float(os.getenv("SIMILARITY_THRESHOLD", "0.7")),
        "distance_metric": os.getenv("DISTANCE_METRIC", "cosine"),
    }

    # Embedding Config
    EMBEDDING_CONFIG: Dict[str, Any] = {
        "model": os.getenv("EMBEDDING_MODEL", "EmbeddingsGigaR"),
        "dimension": int(os.getenv("EMBEDDING_DIMENSION", "1024")),
    }

    # Chunking Config
    # Chunking Config
    CHUNKING_CONFIG: Dict[str, Any] = {
        "chunk_size": int(os.getenv("CHUNK_SIZE", "500")),
        "chunk_overlap": int(os.getenv("CHUNK_OVERLAP", "50")),
        "text_splitter_type": os.getenv("TEXT_SPLITTER_TYPE", "recursive"),
        "top_k_results": int(os.getenv("TOP_K_RESULTS", "5")),
    }

    @model_validator(mode='after')
    def validate_weights(self) -> 'Settings':
        bm25_w = self.SEARCH_CONFIG.get("bm25_weight", 0.5)
        vector_w = self.SEARCH_CONFIG.get("vector_weight", 0.5)
        if abs(bm25_w + vector_w - 1.0) > 1e-6:
            raise ValueError(f"BM25 weight ({bm25_w}) + Vector weight ({vector_w}) must equal 1.0")
        return self
        
    @model_validator(mode='after')
    def validate_sensitive_fields(self) -> 'Settings':
        """Strip whitespace from sensitive fields to prevent auth errors."""
        if self.GIGACHAT_CREDENTIALS:
            self.GIGACHAT_CREDENTIALS = self.GIGACHAT_CREDENTIALS.strip()
        if self.GIGACHAT_CLIENT_ID:
            self.GIGACHAT_CLIENT_ID = self.GIGACHAT_CLIENT_ID.strip()
        if self.GIGACHAT_CLIENT_SECRET:
            self.GIGACHAT_CLIENT_SECRET = self.GIGACHAT_CLIENT_SECRET.strip()
        if self.LANGGRAPH_SERVER_CONFIG and self.LANGGRAPH_SERVER_CONFIG.get("api_key"):
            self.LANGGRAPH_SERVER_CONFIG["api_key"] = self.LANGGRAPH_SERVER_CONFIG["api_key"].strip()
        return self

    # Session Config
    SESSION_CONFIG: Dict[str, Any] = {
        "ttl": 3600,  # 1 hour
    }

    # LangGraph Server Config
    LANGGRAPH_SERVER_CONFIG: Dict[str, Any] = {
        "api_url": "http://localhost:8000",
        "api_key": os.getenv("LANGGRAPH_API_KEY", ""),
    }

    # =================================
    # DATABASE CONFIGS
    # =================================
    POSTGRES_HOST: str = ""
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""
    POSTGRES_URL: Optional[str] = None
    DATABASE_URL: Optional[str] = None
    
    NEO4J_URI: str = ""
    NEO4J_USERNAME: str = ""
    NEO4J_PASSWORD: str = ""
    CHROMA_SERVER_HOST: str = ""
    CHROMA_SERVER_PORT: int = 8001
    CHROMA_SERVER_SSL: bool = True
    CHROMA_DB_PATH: str = "./chroma_db"

    VECTOR_STORE_TYPE: str = "chroma"
    
    DATABASE_TYPE: str = "postgres"

    # =================================
    # COT CONFIG
    # =================================
    COT_CONFIG: Dict[str, Any] = {
        "max_reasoning_depth": int(os.getenv("COT_MAX_REASONING_DEPTH", "4")),
        "max_clarifying_questions": int(os.getenv("COT_MAX_CLARIFYING_QUESTIONS", "5")),
        "enable_verification": os.getenv("COT_ENABLE_VERIFICATION", "True").lower() == "true",
        "neo4j_max_depth": int(os.getenv("COT_NEO4J_MAX_DEPTH", "3")),
        "timeout_per_step": int(os.getenv("COT_TIMEOUT_PER_STEP", "30")),
    }

    # =================================
    # REFLECTION CONFIG
    # =================================
    REFLECTION_CONFIG: Dict[str, Any] = {
        "max_iterations": int(os.getenv("REFLECTION_MAX_ITERATIONS", "3")),
        "quality_threshold": float(os.getenv("REFLECTION_QUALITY_THRESHOLD", "0.8")),
        "critique_temperature": float(os.getenv("REFLECTION_CRITIQUE_TEMP", "0.3")),
        "refinement_temperature": float(os.getenv("REFLECTION_REFINEMENT_TEMP", "0.7")),
    }

    # =================================
    # REASONING CONFIG
    # =================================
    REASONING_CONFIG: Dict[str, Any] = {
        "default_engine": os.getenv("DEFAULT_REASONING_ENGINE", "reflection"),
        "cot": COT_CONFIG,
        "reflection": REFLECTION_CONFIG,
        "task_mapping": {
            "simple_question": "cot",
            "dialogue": "cot",
            "analysis": "cot",
            "complex": "cot"
        }
    }

    # =================================
    # PROVIDER CONFIGS
    # =================================
    GIGACHAT_CREDENTIALS: str = ""
    GIGACHAT_CLIENT_ID: str = ""
    GIGACHAT_CLIENT_SECRET: str = ""
    GIGACHAT_SCOPE: str = "GIGACHAT_API_PERS"

    # =================================
    # LLM EVAL CONFIG
    # =================================
    LLM_EVAL_ENABLED: bool = False
    LLM_EVAL_DATASET: str = "default"
    LLM_EVAL_ENV: str = "production"
    LLM_EVAL_VERSION: str = "1.0.0"
    LLM_EVAL_TIMEOUT_SECONDS: int = 30

    model_config = SettingsConfigDict(
        env_file=_env_files,
        env_file_encoding='utf-8',
        extra='ignore'
    )

    @property
    def DATABASE_CONFIG(self) -> Dict[str, Any]:
        """Get database configuration with all database connection settings."""
        db_url = self.POSTGRES_URL or self.DATABASE_URL
        
        config = {
            "host": self.POSTGRES_HOST,
            "port": self.POSTGRES_PORT,
            "database": self.POSTGRES_DB,
            "user": self.POSTGRES_USER,
            "password": self.POSTGRES_PASSWORD,
            "pool_size": 10,
            "min_size": 10,
            "max_size": 20,
            "timeout": 30,
            "neo4j_uri": self.NEO4J_URI,
            "neo4j_user": self.NEO4J_USERNAME,
            "neo4j_password": self.NEO4J_PASSWORD,
            "chroma_host": self.CHROMA_SERVER_HOST,
            "chroma_port": self.CHROMA_SERVER_PORT,
            "chroma_ssl": self.CHROMA_SERVER_SSL,
        }

        # Parse DATABASE_URL if provided
        if db_url:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(db_url)
                if parsed.hostname: config["host"] = parsed.hostname
                if parsed.port: config["port"] = parsed.port
                if parsed.path.lstrip("/"): config["database"] = parsed.path.lstrip("/")
                if parsed.username: config["user"] = parsed.username
                if parsed.password: config["password"] = parsed.password
            except Exception:
                pass
        
        return config
    
    def get_model_config(self, model_name: str) -> Dict[str, Any]:
        """
        Получить конфигурацию для указанной модели.
        
        Args:
            model_name: Имя модели (gigachat, gigachat_pro, gigachat_max)
            
        Returns:
            Словарь с конфигурацией модели
        """
        configs = {
            "gigachat": self.GIGACHAT_BASE_CONFIG,
            "gigachat_base": self.GIGACHAT_BASE_CONFIG,
            "gigachat_pro": self.GIGACHAT_PRO_CONFIG,
            "gigachat_max": self.GIGACHAT_MAX_CONFIG,
        }
        return configs.get(model_name.lower(), self.GIGACHAT_BASE_CONFIG)
    
    def get_available_models(self) -> List[str]:
        """Получить список доступных моделей."""
        return ["gigachat", "gigachat_pro", "gigachat_max"]


settings = Settings()
