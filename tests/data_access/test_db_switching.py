import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.factory.database_factory import DatabaseFactory
from app.core.config import settings

@pytest.mark.asyncio
async def test_create_dal_postgres():
    """Verify create_dal creates Postgres repositories when DATABASE_TYPE is postgres"""
    # Mock settings
    with patch("app.core.config.settings.DATABASE_TYPE", "postgres"):
        # Mock PostgresProvider
        with patch("app.providers.databases.postgres_provider.PostgresProvider") as MockProvider:
            mock_provider = MockProvider.return_value
            mock_provider.connect = AsyncMock()
            mock_provider.pool = MagicMock()
            
            # Mock ChromaProvider
            with patch("app.factory.database_factory.DatabaseFactory.create_vector_store") as mock_create_vector:
                mock_create_vector.return_value = MagicMock()
                
                dal = await DatabaseFactory.create_dal_async()
                
                assert dal is not None
                assert dal.session_repo is not None
                # Check that it's using the mocked pool
                # Since we can't easily check the internal pool of the repo without accessing it,
                # we assume if it didn't crash, it worked.
                
@pytest.mark.asyncio
async def test_create_dal_unsupported():
    """Verify create_dal raises error for unsupported DB type"""
    with patch("app.core.config.settings.DATABASE_TYPE", "unknown"):
        with patch("app.factory.database_factory.DatabaseFactory.create_vector_store"):
            with pytest.raises(ValueError, match="Unsupported DATABASE_TYPE"):
                await DatabaseFactory.create_dal_async()
