"""004 T010/T014 — cache keyed by (principal, permission epoch, module epoch); role change and module toggle
invalidate it through the epoch consumer; ETag/304 on /me/navigation; live ``navigation.changed``."""

from datetime import UTC, datetime
from uuid import uuid4

import httpx
from fastapi import FastAPI
from sqlalchemy import text

from portalab.capabilities.events import Envelope
from tests.authz_fixtures import insert_user, user
from tests.integration.identity.helpers import create_user, login, module_of
from tests.integration.shell.conftest import ShellHarness


class Ctx:
    replay = False
    as_of = datetime(2026, 10, 1, tzinfo=UTC)

    def __init__(self) -> None:
        self.seen: set[str] = set()

    async def idempotent_effect(self, key: str) -> bool:
        if key in self.seen:
            return False
        self.seen.add(key)
        return True


def envelope(event_type: str, payload: dict[str, object] | None = None) -> Envelope:
    at = datetime(2026, 10, 1, tzinfo=UTC)
    return Envelope(
        uuid4(), 1, event_type, 1, at, at, "x", None, None, "system", None, None, payload or {}, {}, None
    )


async def test_cache_and_epoch_invalidation(sh: ShellHarness) -> None:
    viewer = user(await insert_user(sh.full.database))
    first = await sh.module.assembler.build(viewer)
    assert await sh.module.assembler.build(viewer) is first  # cached
    consumer = sh.consumers.get("shell.navigation_epochs")
    assert consumer is not None
    ctx = Ctx()
    event = envelope("permission.role_assigned")
    await consumer.handler(event, ctx)  # type: ignore[arg-type]
    await consumer.handler(event, ctx)  # type: ignore[arg-type] — redelivery bumps once
    assert await sh.module.epochs.current() == (1, 0)
    assert await sh.module.assembler.build(viewer) is not first  # rebuilt after the bump
    await consumer.handler(envelope("admin.module_toggled"), ctx)  # type: ignore[arg-type]
    await consumer.handler(envelope("admin.config_changed", {"keys": ["identity.x"]}), ctx)  # type: ignore[arg-type]
    await consumer.handler(envelope("admin.config_changed", {"keys": ["shell.navigation.layout"]}), ctx)  # type: ignore[arg-type]
    assert await sh.module.epochs.current() == (1, 2)
    async with sh.full.database.session() as session:
        topics = (
            await session.execute(text("SELECT topic, payload FROM core.live_event ORDER BY seq"))
        ).all()
    assert [t for t, _ in topics] == ["navigation.changed"] * 3
    assert all(set(payload) == {"version"} for _, payload in topics)  # version only, no names


async def test_etag_304(app: FastAPI, client: httpx.AsyncClient, sh: ShellHarness) -> None:
    await create_user(module_of(app), "reader")
    await login(client, "reader")
    first = await client.get("/api/v1/me/navigation")
    assert first.status_code == 200 and first.headers["ETag"]
    assert next(g["key"] for g in first.json()["groups"]) == "main"
    again = await client.get("/api/v1/me/navigation", headers={"If-None-Match": first.headers["ETag"]})
    assert again.status_code == 304
