"""Observability integration fixtures."""

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from portalab.core.db import Database
from portalab.core.time import FixedClock
from tests.integration.privacy.conftest import NOW
from tests.observability_fixtures import ObsHarness, make_observability


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def ob(database: Database, tmp_path: Path, clock: FixedClock) -> ObsHarness:
    return await make_observability(database, tmp_path / "blobs", clock)


@pytest.fixture
def app(ob: ObsHarness, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app

    full = ob.hl.cn.full
    return create_app(
        database=full.database,
        migration_heads=heads,
        identity=full.identity,
        authz=full.authz,
        privacy=full.privacy,
        administration=full.administration,
        events=ob.events,
        connectors=ob.hl.cn.module,
        health=ob.hl.module,
        observability=ob.module,
        static_dir=None,
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http
