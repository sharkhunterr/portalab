"""004 T033/T035 — /me/navigation never exposes unauthorized labels; admin shell routes need shell.manage
(anonymous 401, users 403); the admin layout is validated and audited."""

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from tests.authz_fixtures import make_admin
from tests.integration.identity.helpers import create_user, login, module_of
from tests.integration.shell.conftest import ShellHarness

pytestmark = pytest.mark.integration
ADMIN = [
    ("GET", "/api/v1/admin/shell/layout"),
    ("PUT", "/api/v1/admin/shell/layout"),
    ("GET", "/api/v1/admin/shell/contribution-errors"),
]


async def test_matrix_and_no_leak(app: FastAPI, client: httpx.AsyncClient, sh: ShellHarness) -> None:
    for method, path in [*ADMIN, ("GET", "/api/v1/me/navigation")]:
        assert (await client.request(method, path, json={})).status_code == 401, path
    await create_user(module_of(app), "plain")
    await login(client, "plain")
    for method, path in ADMIN:
        assert (await client.request(method, path, json={})).status_code == 403, path
    body = (await client.get("/api/v1/me/navigation")).text
    for hidden in ("nav.admin", "/admin", "observability", "audit"):
        assert hidden not in body, hidden


async def test_admin_layout(app: FastAPI, client: httpx.AsyncClient, sh: ShellHarness) -> None:
    boss = await create_user(module_of(app), "boss")
    await make_admin(sh.full, boss)
    await login(client, "boss")
    bad = await client.put("/api/v1/admin/shell/layout", json={"order": {"unknown.entry": 0}})
    assert bad.status_code == 422 and bad.json()["code"] == "navigation.contribution_invalid"
    ok = await client.put("/api/v1/admin/shell/layout", json={"pinned": ["health.services"]})
    assert ok.status_code == 200
    nav = (await client.get("/api/v1/me/navigation")).json()
    assert nav["groups"][0]["entries"][0]["key"] == "health.services"
    async with sh.full.database.session() as session:
        audited = await session.scalar(
            text("SELECT count(*) FROM audit.audit_entries WHERE action LIKE 'admin.config%'")
        )
    assert audited and audited >= 1
