"""Real Postgres for store tests: a throwaway container, migrated with the real Alembic revisions.

Tests using these fixtures are marked `db`; they skip (not fail) when Docker is unavailable.
"""

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

API_DIR = Path(__file__).resolve().parents[1]
IMAGE = "postgres:17"  # keep in step with docker-compose.dev.yml

SessionFactory = Callable[[], AsyncSession]


@pytest.fixture
def anyio_backend() -> tuple[str, dict[str, object]]:
    # psycopg's async mode cannot run on the Proactor loop that Windows uses by default.
    # Imported by the db test modules only, so other tests keep the default backend.
    return "asyncio", {"loop_factory": asyncio.SelectorEventLoop}


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    from testcontainers.community.postgres import PostgresContainer

    container = PostgresContainer(IMAGE, driver="psycopg")
    try:
        container.start()
    except Exception as exc:  # Docker missing or not running
        pytest.skip(f"cannot start a Postgres container: {exc}")
    try:
        url = container.get_connection_url()
        # Subprocess: Alembic reconfigures logging, which would leak into other tests.
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=API_DIR,
            env={**os.environ, "DATABASE_URL": url},
            check=True,
            capture_output=True,
        )
        yield url
    finally:
        container.stop()


@pytest.fixture
async def sessions(postgres_url: str) -> AsyncIterator[SessionFactory]:
    """Factory for independent sessions (the concurrency tests need more than one)."""
    engine = create_async_engine(postgres_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE runs, flows"))
    await engine.dispose()
