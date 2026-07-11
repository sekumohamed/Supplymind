# tests/conftest.py
import os
import asyncio
import pytest
import pytest_asyncio

TEST_DB_PATH = "./test_supplymind.db"
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENVIRONMENT"] = "test"

from app.config import get_settings
get_settings.cache_clear()

from app.database import init_db, engine, AsyncSessionLocal
# Import these here, unconditionally, so their tables are always registered
# with Base.metadata BEFORE init_db() runs — regardless of which specific
# test file pytest happens to collect (e.g. running test_rate_limit.py alone
# would otherwise never trigger these imports, and create_all() would create
# zero tables).
from app.models.cache import QueryCache
from app.models.history import QueryHistory
from sqlalchemy import delete


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _setup_test_db():
    await init_db()
    yield
    await engine.dispose()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    yield
    async with AsyncSessionLocal() as session:
        await session.execute(delete(QueryCache))
        await session.execute(delete(QueryHistory))
        await session.commit()