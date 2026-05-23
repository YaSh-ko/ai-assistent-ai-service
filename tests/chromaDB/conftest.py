import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-real-db",
        action="store_true",
        default=False,
        help="Run tests that require a live PostgreSQL and ChromaDB connection.",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "real_db: mark test as requiring a real database connection (skipped by default in CI).",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-real-db"):
        return  # Don't skip anything — user explicitly opted in

    skip_real_db = pytest.mark.skip(reason="Requires live DB — pass --run-real-db to enable")
    for item in items:
        # Skip all tests in the chromaDB directory unless --run-real-db is passed
        if "chromaDB" in str(item.fspath):
            item.add_marker(skip_real_db)
