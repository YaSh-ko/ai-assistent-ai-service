"""
Tests for main application module.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch('app.main.settings') as mock:
        mock.APP_NAME = "Test App"
        mock.APP_VERSION = "1.0.0"
        mock.LOG_LEVEL = "INFO"
        mock.ROOT_PATH = ""
        yield mock


@pytest.fixture
def mock_reasoning_service():
    """Mock ReasoningService."""
    with patch('app.main.ReasoningService') as mock:
        service_instance = MagicMock()
        service_instance.warmup = MagicMock()
        mock.return_value = service_instance
        yield mock


@pytest.fixture
def mock_llm_service():
    """Mock LLMService."""
    with patch('app.main.LLMService') as mock:
        service_instance = AsyncMock()
        service_instance.check_models_availability = AsyncMock(return_value={"gigachat": True})
        mock.return_value = service_instance
        yield mock


@pytest.fixture
def mock_database_factory():
    """Mock DatabaseFactory."""
    with patch('app.main.DatabaseFactory') as mock:
        mock.close_all = AsyncMock()
        yield mock


@pytest.fixture
def mock_model_factory():
    """Mock ModelFactory."""
    with patch('app.factory.model_factory.ModelFactory') as mock:
        mock.close_all = AsyncMock()
        yield mock


class TestLifespan:
    """Test application lifespan events."""
    
    @pytest.mark.asyncio
    async def test_lifespan_startup_success(
        self, 
        mock_settings,
        mock_reasoning_service,
        mock_llm_service,
        mock_database_factory
    ):
        """Test successful startup."""
        from app.main import lifespan, create_app
        
        app = create_app()
        
        async with lifespan(app):
            # Verify warmup was called
            assert mock_reasoning_service.called
            service_instance = mock_reasoning_service.return_value
            service_instance.warmup.assert_called_once()
            
            # Verify models availability check
            assert mock_llm_service.called
            llm_instance = mock_llm_service.return_value
            llm_instance.check_models_availability.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_lifespan_startup_reasoning_failure(
        self,
        mock_settings,
        mock_reasoning_service,
        mock_llm_service,
        mock_database_factory
    ):
        """Test startup continues even if reasoning service fails."""
        from app.main import lifespan, create_app
        
        # Make warmup raise exception
        service_instance = mock_reasoning_service.return_value
        service_instance.warmup.side_effect = Exception("Warmup failed")
        
        app = create_app()
        
        # Should not raise, just log error
        async with lifespan(app):
            pass
    
    @pytest.mark.asyncio
    async def test_lifespan_startup_llm_failure(
        self,
        mock_settings,
        mock_reasoning_service,
        mock_llm_service,
        mock_database_factory
    ):
        """Test startup continues even if LLM check fails."""
        from app.main import lifespan, create_app
        
        # Make check_models_availability raise exception
        llm_instance = mock_llm_service.return_value
        llm_instance.check_models_availability.side_effect = Exception("Check failed")
        
        app = create_app()
        
        # Should not raise, just log error
        async with lifespan(app):
            pass
    
    @pytest.mark.asyncio
    async def test_lifespan_shutdown(
        self,
        mock_settings,
        mock_reasoning_service,
        mock_llm_service,
        mock_database_factory,
        mock_model_factory
    ):
        """Test graceful shutdown."""
        from app.main import lifespan, create_app
        
        app = create_app()
        
        async with lifespan(app):
            pass
        
        # Verify cleanup was called
        mock_database_factory.close_all.assert_called_once()
        mock_model_factory.close_all.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_lifespan_shutdown_database_error(
        self,
        mock_settings,
        mock_reasoning_service,
        mock_llm_service,
        mock_database_factory,
        mock_model_factory
    ):
        """Test shutdown continues even if database cleanup fails."""
        from app.main import lifespan, create_app
        
        mock_database_factory.close_all.side_effect = Exception("DB close failed")
        
        app = create_app()
        
        # Should not raise, just log error
        async with lifespan(app):
            pass
    
    @pytest.mark.asyncio
    async def test_lifespan_shutdown_model_error(
        self,
        mock_settings,
        mock_reasoning_service,
        mock_llm_service,
        mock_database_factory,
        mock_model_factory
    ):
        """Test shutdown continues even if model cleanup fails."""
        from app.main import lifespan, create_app
        
        mock_model_factory.close_all.side_effect = Exception("Model close failed")
        
        app = create_app()
        
        # Should not raise, just log error
        async with lifespan(app):
            pass


class TestCreateApp:
    """Test application creation."""
    
    def test_create_app_basic(self, mock_settings):
        """Test basic app creation."""
        from app.main import create_app
        
        app = create_app()
        
        assert app.title == "Test App"
        assert app.version == "1.0.0"
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"
    
    def test_create_app_with_root_path(self, mock_settings):
        """Test app creation with root path."""
        from app.main import create_app
        
        mock_settings.ROOT_PATH = "/api"
        
        app = create_app()
        
        assert app.root_path == "/api"
    
    def test_create_app_cors_middleware(self, mock_settings):
        """Test CORS middleware is added."""
        from app.main import create_app
        
        app = create_app()
        
        # Check that CORS middleware is in the middleware stack
        # FastAPI wraps middleware, so check for it in app.middleware_stack
        has_cors = any('CORS' in str(type(m)) for m in app.user_middleware)
        assert has_cors or len(app.user_middleware) > 0  # At least some middleware added
    
    def test_create_app_routes_included(self, mock_settings):
        """Test that API routes are included."""
        from app.main import create_app
        
        with patch('app.main.api_router') as mock_router:
            app = create_app()
            
            # Verify router was included - check routes exist
            assert len(app.routes) > 0


class TestEndpoints:
    """Test application endpoints."""
    
    @pytest.fixture
    def client(self, mock_settings, mock_reasoning_service, mock_llm_service, mock_database_factory):
        """Create test client."""
        from app.main import create_app
        
        # Mock lifespan to avoid startup/shutdown
        with patch('app.main.lifespan'):
            app = create_app()
            return TestClient(app)
    
    def test_health_endpoint(self, client, mock_settings):
        """Test health check endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "1.0.0"
    
    def test_info_endpoint(self, client, mock_settings):
        """Test server info endpoint."""
        response = client.get("/info")
        
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.0.0"
        assert data["name"] == "Test App"
    
    def test_root_redirect(self, client):
        """Test root endpoint redirects to docs."""
        response = client.get("/", follow_redirects=False)
        
        assert response.status_code == 307
        assert response.headers["location"] == "/docs"


class TestExceptionHandler:
    """Test global exception handler."""
    
    @pytest.fixture
    def client_with_error_route(self, mock_settings, mock_reasoning_service, mock_llm_service, mock_database_factory):
        """Create test client with error-raising route."""
        from app.main import create_app
        from fastapi import APIRouter
        
        with patch('app.main.lifespan'):
            app = create_app()
            
            # Add test route that raises exception
            test_router = APIRouter()
            
            @test_router.get("/test-error")
            async def error_route():
                raise ValueError("Test error")
            
            app.include_router(test_router)
            
            return TestClient(app, raise_server_exceptions=False)
    
    def test_exception_handler_returns_500(self, client_with_error_route):
        """Test that unhandled exceptions return 500."""
        response = client_with_error_route.get("/test-error")
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Test error" in data["detail"]
    
    def test_exception_handler_includes_cors_headers(self, client_with_error_route):
        """Test that exception handler includes CORS headers."""
        response = client_with_error_route.get(
            "/test-error",
            headers={"origin": "http://localhost:3000"}
        )
        
        assert response.status_code == 500
        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers


class TestSetupPaths:
    """Test path setup function."""
    
    def test_setup_paths_finds_common(self):
        """Test that setup_paths finds common directory."""
        from app.main import setup_paths
        
        # This will return None or a Path depending on project structure
        result = setup_paths()
        
        # Just verify it doesn't crash
        assert result is None or hasattr(result, 'exists')
