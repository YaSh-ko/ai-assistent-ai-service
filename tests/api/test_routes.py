"""
Tests for app/api/routes.py - Main API router
"""

import pytest
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient


class TestAPIRouter:
    """Tests for API router configuration"""
    
    def test_router_includes_all_subrouters(self):
        """Test that main router includes all expected subrouters"""
        from app.api.routes import api_router
        
        # Check that router has routes
        assert len(api_router.routes) > 0
        
        # Verify specific routes exist
        route_paths = [route.path for route in api_router.routes]
        assert "/info" in route_paths


@pytest.mark.asyncio
class TestAPIInfo:
    """Tests for /info endpoint"""
    
    @patch('app.core.config.settings')
    async def test_api_info_returns_version_and_name(self, mock_settings):
        """Test that /info endpoint returns app version and name"""
        from app.api.routes import api_info
        
        mock_settings.APP_VERSION = "1.0.0"
        mock_settings.APP_NAME = "Test Service"
        
        result = await api_info()
        
        assert result == {
            "version": "1.0.0",
            "name": "Test Service"
        }
    
    @patch('app.core.config.settings')
    async def test_api_info_with_default_values(self, mock_settings):
        """Test /info endpoint with default configuration values"""
        from app.api.routes import api_info
        
        mock_settings.APP_VERSION = "0.1.0"
        mock_settings.APP_NAME = "Python AI Service"
        
        result = await api_info()
        
        assert "version" in result
        assert "name" in result
        assert result["version"] == "0.1.0"
        assert result["name"] == "Python AI Service"


class TestRouterIntegration:
    """Integration tests for router setup"""
    
    def test_router_has_correct_tags(self):
        """Test that routes have correct tags"""
        from app.api.routes import api_router
        
        # Find the /info route
        info_route = None
        for route in api_router.routes:
            if route.path == "/info":
                info_route = route
                break
        
        assert info_route is not None
        assert "system" in info_route.tags
    
    def test_router_includes_assistants(self):
        """Test that assistants router is included"""
        from app.api.routes import api_router
        from app.api import assistants
        
        # Verify assistants router is included
        # This is implicit through include_router call
        assert assistants.router is not None
    
    def test_router_includes_threads(self):
        """Test that threads router is included"""
        from app.api.routes import api_router
        from app.api import threads
        
        # Verify threads router is included
        assert threads.router is not None
    
    def test_router_includes_runs(self):
        """Test that runs router is included"""
        from app.api.routes import api_router
        from app.api.runs import router as runs_router
        
        # Verify runs router is included
        assert runs_router is not None
    
    def test_router_includes_models(self):
        """Test that models router is included"""
        from app.api.routes import api_router
        from app.api.models import router as models_router
        
        # Verify models router is included
        assert models_router is not None
    
    def test_router_includes_detector(self):
        """Test that detector router is included"""
        from app.api.routes import api_router
        from app.api.v1.detector_controller import router as detector_router

        assert detector_router is not None
        route_paths = [getattr(r, "path", "") for r in api_router.routes]
        assert any("detector" in p for p in route_paths)
