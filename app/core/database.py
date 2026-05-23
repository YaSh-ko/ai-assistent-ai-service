from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings
from functools import lru_cache
import sys
import os
from pathlib import Path

# Find Philosophy root
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

# Import Base from shared common package
from common.database.connection import Base

@lru_cache()
def get_engine():
    """Create a new engine once and cache it."""
    async_url = settings.POSTGRES_URL
    if async_url and not async_url.startswith("postgresql+asyncpg://"):
        async_url = async_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    if not async_url:
        return None
        
    return create_async_engine(async_url, echo=settings.DEBUG)

@lru_cache()
def get_session_maker():
    """Create a sessionmaker once and cache it."""
    engine = get_engine()
    if engine:
        return async_sessionmaker(engine, expire_on_commit=False)
    return None

async def get_async_session():
    """Dependency for FastAPI or other async contexts."""
    session_maker = get_session_maker()
    if not session_maker:
        raise RuntimeError("Database engine not initialized. Check POSTGRES_URL.")
    
    async with session_maker() as session:
        yield session
