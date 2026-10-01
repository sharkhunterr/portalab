"""T023 — /healthz 200; /readyz 503 problem+json when the database is unreachable."""

import httpx
from sqlalchemy.pool import NullPool

from portalab.app.main import create_app
from portalab.core.db import Database


async def test_healthz_is_ok_without_database(heads: set[str]) -> None:
    app = create_app(migration_heads=heads)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz_ok_on_migrated_database(database: Database, heads: set[str]) -> None:
    app = create_app(database=database, migration_heads=heads)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/readyz")
    assert response.status_code == 200


async def test_readyz_503_problem_when_database_unreachable(heads: set[str]) -> None:
    unreachable = Database.from_url(
        "postgresql+asyncpg://nobody:nopass@127.0.0.1:1/none", poolclass=NullPool, connect_args={"timeout": 2}
    )
    app = create_app(database=unreachable, migration_heads=heads)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/readyz", headers={"X-Correlation-Id": "probe-1"})
    finally:
        await unreachable.dispose()
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "not_ready.database"
    assert body["correlation_id"] == "probe-1"
    assert "nopass" not in response.text
    assert "127.0.0.1" not in response.text
