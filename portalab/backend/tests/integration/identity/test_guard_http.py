"""028 (US3, SC-006): a member probing the administration is blocked — every session signed out, signing in
again changes nothing, a restart changes nothing; the block lifted, they are back."""

import asyncio
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from portalab.app.main import guard_of, security_alert
from portalab.app.security import _ALERTS
from portalab.capabilities.catalog import new_registry
from portalab.core.db import Database
from portalab.modules.identity.guard import BlockStore
from tests.integration.identity.helpers import create_user, login, module_of


def households(app: FastAPI) -> Any:
    """032: the household module's service (the households are no longer identity's)."""
    return app.state.household_module.service


pytestmark = pytest.mark.integration


class Audit:
    def __init__(self) -> None:
        self.entries: list[Any] = []

    async def record(self, session: Any, entry: Any) -> None:
        self.entries.append(entry)


def _armed(app: FastAPI, database: Database, audit: Audit) -> BlockStore:
    store = BlockStore(database)
    platform = SimpleNamespace(
        authz=SimpleNamespace(audit=audit), notifications=SimpleNamespace(capabilities=new_registry())
    )
    app.state.security_blocks = store
    app.state.security_alert = security_alert(database, platform, guard_of(app), store)
    return store


async def _settle() -> None:
    while _ALERTS:
        await asyncio.gather(*list(_ALERTS), return_exceptions=True)


async def test_a_member_probing_the_administration_is_kept_out(
    app: FastAPI, client: httpx.AsyncClient, database: Database
) -> None:
    audit = Audit()
    store = _armed(app, database, audit)
    await create_user(module_of(app), "mallory")
    assert (await login(client, "mallory")).status_code == 200
    statuses = [(await client.get("/api/v1/admin/visuals")).status_code for _ in range(12)]
    await _settle()
    assert statuses[0] == 403 and statuses[-1] == 403
    blocked = await client.get("/api/v1/me")
    assert blocked.status_code in (401, 403)  # signed out (its sessions revoked) or refused
    assert any(e.action == "security.blocked" for e in audit.entries)
    # signing in again changes nothing
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token", None)
    assert (await login(client, "mallory")).status_code == 200
    again = await client.get("/api/v1/me")
    assert again.status_code == 403 and again.json()["code"] == "security.blocked"
    # nor does a restart: a fresh process's memory holds nothing — it loads the stored blocks
    guard = guard_of(app)
    guard._blocks.clear()
    guard._users.clear()
    guard._stored.clear()
    guard.load(await store.active())
    client.cookies.clear()
    client.headers.pop("X-CSRF-Token", None)
    assert (await login(client, "mallory")).status_code == 200
    assert (await client.get("/api/v1/me")).status_code == 403
    # lifted (by an administrator or from the console): back
    assert await store.lift(by="console:test", subject="mallory") >= 1
    guard.load(await store.active())
    assert (await client.get("/api/v1/me")).status_code == 200


async def test_a_household_profile_refused_by_its_masters_rules_is_no_probe(
    app: FastAPI, client: httpx.AsyncClient, database: Database
) -> None:
    """032: a child profile opening locked titles and withheld features over and over is its master's rules
    at work — never a block of the master's account; the administration still counts."""
    from portalab.core.authz_port import Principal

    audit = Audit()
    _armed(app, database, audit)
    module = module_of(app)
    owner = await create_user(module, "parent")
    created = await households(app).create(
        Principal(user_id=owner), display_name="Arthur", kind="child", color=None, pin=None
    )
    assert (await login(client, "parent")).status_code == 200
    await client.post("/api/v1/household/switch", json={"user_id": str(created["id"])})
    refused = [
        (await client.post("/api/v1/household/profiles", json={"display_name": "X"})).status_code
        for _ in range(30)
    ]
    await _settle()
    assert set(refused) == {403}
    assert (await client.get("/api/v1/me")).status_code == 200  # nothing blocked
    assert not any(e.action == "security.blocked" for e in audit.entries)
    for _ in range(12):  # probing the administration still counts double
        await client.get("/api/v1/admin/visuals")
    await _settle()
    assert any(e.action == "security.blocked" for e in audit.entries)
