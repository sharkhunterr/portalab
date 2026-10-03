"""Authorization integration fixtures (real PostgreSQL, real engine, catalog synced)."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from portalab.core.db import Database
from portalab.core.time import FixedClock
from tests.authz_fixtures import AuthzPlatform, make_administration, make_platform

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
async def platform(database: Database, tmp_path: Path, clock: FixedClock) -> AuthzPlatform:
    built = make_platform(database, tmp_path / "blobs", clock)
    await built.authz.catalog.sync()
    return built


@pytest.fixture
def app(platform: AuthzPlatform, heads: set[str]) -> FastAPI:
    from portalab.app.main import create_app
    from portalab.modules.events.module import EventsModule
    from portalab.modules.privacy.module import PrivacyModule
    from portalab.modules.privacy.settings import SecurityConfig

    privacy = PrivacyModule(
        platform.database, platform.authz.engine.events, platform.authz.audit, platform.identity.capabilities
    )
    privacy.register_capabilities()
    administration = make_administration(platform)
    return create_app(
        database=platform.database,
        migration_heads=heads,
        identity=platform.identity,
        authz=platform.authz,
        privacy=privacy,
        administration=administration,
        events=EventsModule(platform.database, platform.authz.audit, platform.identity.capabilities),
        static_dir=None,
        # the permission matrix sweeps every route in one minute: keep the limiter out of its way
        security_config=SecurityConfig(
            rate_limit_per_ip_per_minute=10_000, rate_limit_per_user_per_minute=10_000
        ),
    )


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://portal.test"
    ) as http:
        yield http
