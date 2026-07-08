# tests/conftest.py
import os
import asyncio
import pytest
import pytest_asyncio

TEST_DB_PATH = "./test_supplymind.db"
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

# MUST happen before any `app.*` module is imported anywhere in the test session,
# since app/database.py builds its engine at import time from settings.database_url.
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENVIRONMENT"] = "test"

from app.config import get_settings  # noqa: E402
get_settings.cache_clear()  # in case anything imported settings before conftest ran

from app.database import init_db, engine  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _setup_test_db():
    """Create schema once for the whole test session, drop the file after."""
    await init_db()
    yield
    await engine.dispose()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    """Wipe rows between tests so tests don't leak state into each other."""
    from app.database import AsyncSessionLocal
    from app.models.cache import QueryCache
    from app.models.history import QueryHistory
    from sqlalchemy import delete

    yield
    async with AsyncSessionLocal() as session:
        await session.execute(delete(QueryCache))
        await session.execute(delete(QueryHistory))
        await session.commit()