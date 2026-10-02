"""Health integration fixtures."""

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from portalab.core.db import Database
from portalab.core.time import FixedClock
from tests.health_fixtures import HealthHarness, make_health
from tests.integration.privacy.conftest import NOW


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def hl(database: Database, tmp_path: Path, clock: FixedClock) -> HealthHarness:
    return await make_health(database, tmp_path / "blobs", clock)


@pytest.fixture
def app(hl: HealthHarness, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    full = hl.cn.full
    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        connectors=hl.cn.module,
        health=hl.module,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http
