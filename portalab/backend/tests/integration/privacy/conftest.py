"""Privacy integration fixtures: the full platform on a fresh migrated database."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from portalab.core.db import Database
from portalab.core.time import FixedClock
from tests.privacy_fixtures import FullPlatform, make_full_platform

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def full(database: Database, tmp_path: Path, clock: FixedClock) -> FullPlatform:
    built = make_full_platform(database, tmp_path / "blobs", clock)
    await built.authz.catalog.sync()
    return built


@pytest.fixture
def app(full: FullPlatform, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http
