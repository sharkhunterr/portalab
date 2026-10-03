"""023 T018 — data is deleted only by ``POST /admin/plugins/{key}/purge`` (``plugins.purge``,
confirmation, audit), refused while enabled; an optional export comes first; schema and role dropped;
the purge is recorded; core data unaffected."""

import json
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.integration.identity.helpers import login
from tests.integration.plugins.conftest import SYSTEM, PlHarness

pytestmark = pytest.mark.integration


async def test_purge(pl: PlHarness, client: AsyncClient) -> None:
    await pl.installed(pl.hello())
    greet = pl.registries.routes.get("hello", "POST", "greet")
    assert greet is not None
    await greet.handler(SYSTEM, {}, {"name": "Grace"})
    async with pl.database.session() as session:
        users_before = await session.scalar(text("SELECT count(*) FROM identity.users"))
    await login(client, "ursula")
    assert (await client.post("/api/v1/admin/plugins/hello/purge", json={})).status_code == 403
    await login(client, "boss")
    enabled = await client.post("/api/v1/admin/plugins/hello/purge", json={})
    assert enabled.status_code == 409 and enabled.json()["code"] == "authz.confirmation_required"
    confirmed = await client.post(
        "/api/v1/admin/plugins/hello/purge", json={"confirmation": enabled.json()["confirmation"]}
    )
    assert confirmed.status_code == 409 and confirmed.json()["code"] == "plugin.enabled"
    await client.post("/api/v1/admin/plugins/hello/disable", json={})
    first = await client.post("/api/v1/admin/plugins/hello/purge", json={"export": True})
    done = await client.post(
        "/api/v1/admin/plugins/hello/purge",
        json={"export": True, "confirmation": first.json()["confirmation"]},
    )
    assert done.status_code == 200 and done.json()["schema_dropped"] is True
    exported = json.loads(Path(done.json()["export_ref"]).read_text())  # noqa: ASYNC240
    assert [row["name"] for row in exported["greetings"]] == ["Grace"]
    async with pl.database.session() as session:
        schema = await session.scalar(
            text("SELECT count(*) FROM information_schema.schemata WHERE schema_name = 'plugin_hello'")
        )
        role = await session.scalar(
            text("SELECT count(*) FROM pg_roles WHERE rolname = :r"), {"r": pl.module.storage.role("hello")}
        )
        purges = await session.scalar(text("SELECT count(*) FROM plugins.purges WHERE exported"))
        users_after = await session.scalar(text("SELECT count(*) FROM identity.users"))
        audited = await session.scalar(
            text("SELECT count(*) FROM audit.audit_entries WHERE action = 'plugin.purged'")
        )
    assert (schema, role, purges, audited) == (0, 0, 1, 1) and users_after == users_before
