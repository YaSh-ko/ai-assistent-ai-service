"""
Главный роутер API.
Объединяет все API endpoints.
"""

from fastapi import APIRouter
from app.api import assistants, threads
from app.api.runs import router as runs_router

from app.api.v1.detector_controller import router as detector_router
from app.api.v1.insights_controller import router as insights_router

api_router = APIRouter()

api_router.include_router(assistants.router)
api_router.include_router(threads.router)
api_router.include_router(runs_router)

api_router.include_router(detector_router)
api_router.include_router(insights_router)


@api_router.get("/info", tags=["system"])
async def api_info():
    """LangGraph SDK compatibility: server info (under /api/v1 prefix)."""
    from app.core.config import settings
    return {
        "version": settings.APP_VERSION,
        "name": settings.APP_NAME,
    }
