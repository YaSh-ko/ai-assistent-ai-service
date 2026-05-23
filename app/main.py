import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
try:
    from prometheus_client import make_asgi_app as _make_asgi_app
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False
    _make_asgi_app = None
import sys
from pathlib import Path

# Setup paths to find Philosophy/common
def setup_paths():
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "common").exists():
            root_str = str(parent)
            if root_str not in sys.path:
                sys.path.insert(0, root_str)
            return parent
    return None

setup_paths()

from app.core.config import settings
from app.api.routes import api_router
from app.services.reasoning_service import ReasoningService
from app.services.llm_service import LLMService
from app.factory.database_factory import DatabaseFactory
from fastapi import Request
from fastapi.responses import JSONResponse

# Setup logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events: startup and shutdown.
    """
    # Startup
    logger.info("Starting up...")
    
    # 1. Warmup reasoning service
    try:
        service = ReasoningService()
        service.warmup()
    except Exception as e:
        logger.error(f"Failed to warmup reasoning service: {e}")
        
    # 2. Check models availability
    try:
        llm_service = LLMService()
        availability = await llm_service.check_models_availability()
        logger.info(f"Models availability: {availability}")
    except Exception as e:
        logger.error(f"Failed to check models availability: {e}")
        
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    
    # Graceful shutdown of database connections
    try:
        await DatabaseFactory.close_all()
    except Exception as e:
        logger.error(f"Error during database shutdown: {e}")
    
    # Graceful shutdown of model providers
    try:
        from app.factory.model_factory import ModelFactory
        await ModelFactory.close_all()
        logger.info("All model providers closed.")
    except Exception as e:
        logger.error(f"Error during model provider shutdown: {e}")

def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        lifespan=lifespan,
        redirect_slashes=False,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        root_path=getattr(settings, "ROOT_PATH", ""),
    )

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://delez.tech",
            "https://www.delez.tech",
            "https://api.delez-repo.ru",
            "https://delez-repo.ru",
            "http://localhost:5173",
            "http://localhost:3000",
            "http://localhost:3001",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # Routes
    app.include_router(api_router, prefix="/api/v1")

    # --- Prometheus metrics endpoint ---
    if _PROMETHEUS_AVAILABLE and _make_asgi_app:
        metrics_app = _make_asgi_app()
        app.mount("/metrics", metrics_app)

    # --- HTTP Metrics Middleware ---
    from app.monitoring.metrics import (
        ai_requests_total,
        ai_request_duration_seconds,
        ai_active_requests,
    )

    @app.middleware("http")
    async def prometheus_middleware(request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)

        endpoint = request.url.path
        ai_active_requests.inc()
        start = time.time()
        status = "success"
        try:
            response = await call_next(request)
            if response.status_code >= 400:
                status = "error"
            return response
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.time() - start
            ai_requests_total.labels(endpoint=endpoint, status=status).inc()
            ai_request_duration_seconds.labels(endpoint=endpoint).observe(duration)
            ai_active_requests.dec()

    # Global exception handler to ensure CORS headers on errors
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc)},
            headers={
                "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
                "Access-Control-Allow-Credentials": "true",
            }
        )

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "version": settings.APP_VERSION}

    @app.get("/info")
    async def server_info():
        """LangGraph SDK compatibility: server info endpoint."""
        return {
            "version": settings.APP_VERSION,
            "name": settings.APP_NAME,
        }

    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse(url="/docs")

    from fastapi.responses import Response

    @app.middleware("http")
    async def handle_options_requests(request: Request, call_next):
        if request.method == "OPTIONS":
            origin = request.headers.get("Origin", "*")
            requested_headers = request.headers.get(
                "Access-Control-Request-Headers",
                "Content-Type, Authorization, X-Requested-With, Accept, Origin",
            )
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                    "Access-Control-Allow-Headers": requested_headers,
                    "Access-Control-Allow-Credentials": "true",
                    "Access-Control-Max-Age": "86400",
                    "Vary": "Origin, Access-Control-Request-Headers",
                },
            )
        response = await call_next(request)
        origin = request.headers.get("Origin")
        if origin:
            response.headers["Vary"] = "Origin"
        return response

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
