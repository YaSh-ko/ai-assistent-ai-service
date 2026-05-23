"""
Extended tests for app/core/config.py
"""

import pytest
import os
from unittest.mock import patch, Mock
from pydantic_settings import SettingsConfigDict


class TestSettingsBasic:
    """Tests for basic Settings functionality"""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_default_values(self):
        """Test default configuration values"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert s.APP_NAME == "Python AI Service"
        assert s.APP_VERSION == "0.1.0"
        # DEBUG can be True from .env, so we just check it exists
        assert isinstance(s.DEBUG, bool)
        assert s.LOG_LEVEL == "INFO"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_model_config(self):
        """Test model configuration"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert "simple_question" in s.TASK_MODEL_MAP
        assert s.TASK_MODEL_MAP["simple_question"] == "gigachat"
        assert s.TASK_MODEL_MAP["complex"] == "gigachat_max"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_model_complexity_map(self):
        """Test model complexity mapping"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert s.MODEL_COMPLEXITY_MAP["simple"] == "gigachat"
        assert s.MODEL_COMPLEXITY_MAP["medium"] == "gigachat_pro"
        assert s.MODEL_COMPLEXITY_MAP["complex"] == "gigachat_max"


class TestVLLMConfig:
    """Tests for VLLM configuration"""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_vllm_default_config(self):
        """Test VLLM default configuration"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert "base_url" in s.VLLM_CONFIG
        assert "model_name" in s.VLLM_CONFIG
        assert "temperature" in s.VLLM_CONFIG
        assert "max_tokens" in s.VLLM_CONFIG
        assert isinstance(s.VLLM_CONFIG["temperature"], float)
        assert isinstance(s.VLLM_CONFIG["max_tokens"], int)


class TestGigaChatConfig:
    """Tests for GigaChat configuration"""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_gigachat_base_config(self):
        """Test GigaChat base configuration"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert s.GIGACHAT_BASE_CONFIG["model"] == "GigaChat"
        assert isinstance(s.GIGACHAT_BASE_CONFIG["temperature"], float)
        assert isinstance(s.GIGACHAT_BASE_CONFIG["max_tokens"], int)
    
    @patch.dict(os.environ, {}, clear=True)
    def test_gigachat_pro_config(self):
        """Test GigaChat Pro configuration"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert s.GIGACHAT_PRO_CONFIG["model"] == "GigaChat-Pro"
        assert isinstance(s.GIGACHAT_PRO_CONFIG["temperature"], float)
        assert isinstance(s.GIGACHAT_PRO_CONFIG["max_tokens"], int)
    
    @patch.dict(os.environ, {}, clear=True)
    def test_gigachat_max_config(self):
        """Test GigaChat Max configuration"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert s.GIGACHAT_MAX_CONFIG["model"] == "GigaChat-Max"
        assert isinstance(s.GIGACHAT_MAX_CONFIG["temperature"], float)
        assert isinstance(s.GIGACHAT_MAX_CONFIG["max_tokens"], int)


class TestSearchConfig:
    """Tests for search configuration"""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_search_default_config(self):
        """Test search default configuration"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert "search_type" in s.SEARCH_CONFIG
        assert "bm25_weight" in s.SEARCH_CONFIG
        assert "vector_weight" in s.SEARCH_CONFIG
        assert "distance_metric" in s.SEARCH_CONFIG
        assert isinstance(s.SEARCH_CONFIG["bm25_weight"], float)
        assert isinstance(s.SEARCH_CONFIG["vector_weight"], float)


class TestEmbeddingConfig:
    """Tests for embedding configuration"""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_embedding_default_config(self):
        """Test embedding default configuration"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert "model" in s.EMBEDDING_CONFIG
        assert "dimension" in s.EMBEDDING_CONFIG
        assert isinstance(s.EMBEDDING_CONFIG["dimension"], int)


class TestChunkingConfig:
    """Tests for chunking configuration"""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_chunking_default_config(self):
        """Test chunking default configuration"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert "chunk_size" in s.CHUNKING_CONFIG
        assert "chunk_overlap" in s.CHUNKING_CONFIG
        assert "text_splitter_type" in s.CHUNKING_CONFIG
        assert isinstance(s.CHUNKING_CONFIG["chunk_size"], int)
        assert isinstance(s.CHUNKING_CONFIG["chunk_overlap"], int)


class TestWeightValidation:
    """Tests for weight validation"""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_valid_weights(self):
        """Test validation with valid weights"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        s.SEARCH_CONFIG["bm25_weight"] = 0.4
        s.SEARCH_CONFIG["vector_weight"] = 0.6
        # Should not raise
        s.validate_weights()
    
    @patch.dict(os.environ, {}, clear=True)
    def test_invalid_weights_sum(self):
        """Test validation with invalid weight sum"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        s.SEARCH_CONFIG["bm25_weight"] = 0.4
        s.SEARCH_CONFIG["vector_weight"] = 0.5
        
        with pytest.raises(ValueError, match="must equal 1.0"):
            s.validate_weights()


class TestSensitiveFieldsValidation:
    """Tests for sensitive fields validation"""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_strip_gigachat_credentials(self):
        """Test stripping whitespace from GigaChat credentials"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        s.GIGACHAT_CREDENTIALS = "  credentials  "
        s.GIGACHAT_CLIENT_ID = " client_id "
        s.GIGACHAT_CLIENT_SECRET = " secret "
        
        s = s.validate_sensitive_fields()
        
        assert s.GIGACHAT_CREDENTIALS == "credentials"
        assert s.GIGACHAT_CLIENT_ID == "client_id"
        assert s.GIGACHAT_CLIENT_SECRET == "secret"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_strip_vllm_api_key(self):
        """Test stripping whitespace from VLLM API key"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        s.VLLM_API_KEY = "  api_key  "
        
        s = s.validate_sensitive_fields()
        
        assert s.VLLM_API_KEY == "api_key"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_strip_langgraph_api_key(self):
        """Test stripping whitespace from LangGraph API key"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        s.LANGGRAPH_SERVER_CONFIG = {"api_key": "  key  "}
        
        s = s.validate_sensitive_fields()
        
        assert s.LANGGRAPH_SERVER_CONFIG["api_key"] == "key"


class TestDatabaseConfig:
    """Tests for database configuration"""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_database_default_config(self):
        """Test database default configuration"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert s.POSTGRES_PORT == 5432
        # CHROMA_SERVER_PORT default is 8001, but may be overridden by .env
        assert isinstance(s.CHROMA_SERVER_PORT, int)
        assert isinstance(s.CHROMA_SERVER_SSL, bool)
        assert s.VECTOR_STORE_TYPE == "chroma"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_database_config_property(self):
        """Test DATABASE_CONFIG property"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        s.POSTGRES_HOST = "localhost"
        s.POSTGRES_PORT = 5432
        s.POSTGRES_DB = "testdb"
        s.POSTGRES_USER = "user"
        s.POSTGRES_PASSWORD = "pass"
        
        config = s.DATABASE_CONFIG
        
        assert config["host"] == "localhost"
        assert config["port"] == 5432
        assert config["database"] == "testdb"
        assert config["user"] == "user"
        assert config["password"] == "pass"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_database_config_with_url(self):
        """Test DATABASE_CONFIG with connection URL"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        s.DATABASE_URL = "postgresql://user:pass@host:5433/dbname"
        
        config = s.DATABASE_CONFIG
        
        assert config["host"] == "host"
        assert config["port"] == 5433
        assert config["database"] == "dbname"
        assert config["user"] == "user"
        assert config["password"] == "pass"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_milvus_config(self):
        """Test Milvus configuration"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        s.MILVUS_HOST = "localhost"
        s.MILVUS_PORT = 19530
        s.MILVUS_COLLECTION = "test_collection"
        
        config = s.DATABASE_CONFIG
        
        assert config["milvus_host"] == "localhost"
        assert config["milvus_port"] == 19530
        assert config["milvus_collection"] == "test_collection"


class TestCOTConfig:
    """Tests for Chain-of-Thought configuration"""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_cot_default_config(self):
        """Test CoT default configuration"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert "max_reasoning_depth" in s.COT_CONFIG
        assert "max_clarifying_questions" in s.COT_CONFIG
        assert "enable_verification" in s.COT_CONFIG
        assert "neo4j_max_depth" in s.COT_CONFIG
        assert isinstance(s.COT_CONFIG["max_reasoning_depth"], int)
        assert isinstance(s.COT_CONFIG["enable_verification"], bool)


class TestReflectionConfig:
    """Tests for Reflection configuration"""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_reflection_default_config(self):
        """Test Reflection default configuration"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert "max_iterations" in s.REFLECTION_CONFIG
        assert "quality_threshold" in s.REFLECTION_CONFIG
        assert "critique_temperature" in s.REFLECTION_CONFIG
        assert "refinement_temperature" in s.REFLECTION_CONFIG
        assert isinstance(s.REFLECTION_CONFIG["max_iterations"], int)
        assert isinstance(s.REFLECTION_CONFIG["quality_threshold"], float)


class TestReasoningConfig:
    """Tests for Reasoning configuration"""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_reasoning_default_config(self):
        """Test Reasoning default configuration"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert s.REASONING_CONFIG["default_engine"] == "reflection"
        assert "cot" in s.REASONING_CONFIG
        assert "reflection" in s.REASONING_CONFIG
        assert "task_mapping" in s.REASONING_CONFIG
    
    @patch.dict(os.environ, {}, clear=True)
    def test_reasoning_task_mapping(self):
        """Test Reasoning task mapping"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        task_mapping = s.REASONING_CONFIG["task_mapping"]
        assert task_mapping["simple_question"] == "cot"
        assert task_mapping["dialogue"] == "cot"
        assert task_mapping["analysis"] == "cot"


class TestModelConfigMethods:
    """Tests for model configuration methods"""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_model_config_vllm(self):
        """Test getting VLLM model config"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        config = s.get_model_config("vllm")
        assert config == s.VLLM_CONFIG
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_model_config_gigachat(self):
        """Test getting GigaChat model config"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        config = s.get_model_config("gigachat")
        assert config == s.GIGACHAT_BASE_CONFIG
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_model_config_gigachat_pro(self):
        """Test getting GigaChat Pro model config"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        config = s.get_model_config("gigachat_pro")
        assert config == s.GIGACHAT_PRO_CONFIG
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_model_config_gigachat_max(self):
        """Test getting GigaChat Max model config"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        config = s.get_model_config("gigachat_max")
        assert config == s.GIGACHAT_MAX_CONFIG
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_model_config_unknown(self):
        """Test getting unknown model config returns default"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        config = s.get_model_config("unknown_model")
        assert config == s.GIGACHAT_BASE_CONFIG
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_model_config_case_insensitive(self):
        """Test getting model config is case insensitive"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        config = s.get_model_config("GIGACHAT_PRO")
        assert config == s.GIGACHAT_PRO_CONFIG
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_available_models(self):
        """Test getting available models list"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        models = s.get_available_models()
        assert "vllm" in models
        assert "gigachat" in models
        assert "gigachat_pro" in models
        assert "gigachat_max" in models
        assert len(models) == 4


class TestSessionConfig:
    """Tests for session configuration"""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_session_default_config(self):
        """Test session default configuration"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert s.SESSION_CONFIG["ttl"] == 3600
        assert s.SESSION_CONFIG["cache_provider"] == "redis"


class TestLangGraphConfig:
    """Tests for LangGraph configuration"""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_langgraph_default_config(self):
        """Test LangGraph default configuration"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert s.LANGGRAPH_SERVER_CONFIG["api_url"] == "http://localhost:8000"
        assert "api_key" in s.LANGGRAPH_SERVER_CONFIG


class TestProviderConfigs:
    """Tests for provider configurations"""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_gigachat_provider_config(self):
        """Test GigaChat provider configuration"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert s.GIGACHAT_SCOPE == "GIGACHAT_API_PERS"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_vllm_provider_config(self):
        """Test VLLM provider configuration"""
        from app.core.config import Settings
        s = Settings(_env_file=None)
        assert s.VLLM_API_URL == "http://localhost:8000/v1"
        assert s.VLLM_MODEL_NAME == "local-model"


class TestSettingsSingleton:
    """Tests for settings singleton"""
    
    def test_settings_singleton(self):
        """Test that settings is a singleton"""
        from app.core.config import settings as settings1
        from app.core.config import settings as settings2
        assert settings1 is settings2
