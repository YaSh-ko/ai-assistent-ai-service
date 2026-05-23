from app.core.config import settings

def test_database_config_exists():
    """Проверка наличия конфигурации БД"""
    assert hasattr(settings, 'DATABASE_CONFIG')
    
    db_config = settings.DATABASE_CONFIG
    assert 'host' in db_config
    assert 'port' in db_config
    assert 'database' in db_config
    assert 'user' in db_config
    assert 'password' in db_config
    assert 'pool_size' in db_config or 'min_size' in db_config
