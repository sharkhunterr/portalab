"""Identity integration fixtures: a wired :class:`IdentityContext` on a fresh migrated database."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from portalab.core.db import Database
from portalab.core.time import FixedClock
from tests.identity_fakes import IdentityHarness, make_context

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
def harness(database: Database, tmp_path: Path, clock: FixedClock) -> IdentityHarness:
    return make_context(database, tmp_path / "blobs", clock=clock)


@pytest.fixture
def app(harness: IdentityHarness, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    return create_app(
        database=harness.context.database,
        migration_heads=heads,
        identity=harness.context,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="https://portal.test") as http:
        yield http
