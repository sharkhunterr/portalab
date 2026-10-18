"""030 (US1, US2) — a confined plugin end to end: its review lists the capabilities it asks, approving grants
them, enabling starts its process; its route answers members with their rights; its storage runs as its own
role, so nothing it sends reaches Portalab's data or role; a capability it was not granted is refused and
recorded; revoking one takes effect at once (Linux with Landlock ABI ≥ 4)."""

import textwrap
from dataclasses import replace
from typing import Any

import httpx
import pytest
from sqlalchemy import select, text
from tests.integration.identity.helpers import login
from tests.integration.plugins.conftest import PlHarness

from portalab.core.confinement import probe
from portalab.modules.plugins.models import Attempt

pytestmark = pytest.mark.skipif(not probe().ok, reason="kernel cannot confine")

MANIFEST = """
schema_version = 2
key = "probe"
name = "Probe"
version = "1.0.0"
entry_point = "probe_plugin:register"
migrations = "migrations"
permissions = [{ name = "use", description = "Use the probe" }]

[capabilities]
storage = { quota_mb = 5 }
operations = true

[[routes]]
path = "notes"
method = "POST"
permission = "plugin:probe.use"
exposure = "action"

[[routes]]
path = "probe"
method = "GET"
permission = "plugin:probe.use"
exposure = "read"

[[routes]]
path = "outside"
method = "GET"
permission = "plugin:probe.use"
exposure = "read"
"""

CODE = """
from portalab.sdk.confined.recording import Denied

PROBES = {
    "core_table": "SELECT * FROM identity.users LIMIT 1",
    "reset_role": "RESET ROLE",
    "set_role": "SET ROLE portalab",
    "set_config_role": "SELECT set_config('role', 'portalab', false)",
    "two_statements": "SELECT 1; SELECT 2",
    "copy": "COPY (SELECT 1) TO STDOUT",
    "read_file": "SELECT pg_read_file('/etc/passwd')",
    "who": "SELECT current_user AS who",
    "advisory": "SELECT pg_advisory_lock(424242) AS locked",
    "sleep": "SELECT pg_sleep(3)",
}

def register(ctx):
    async def add(principal, query, body):
        params = {"a": str(principal.user_id), "b": body["text"]}
        await ctx.db.execute("INSERT INTO notes (author, body) VALUES (:a, :b)", params)
        rows = await ctx.db.execute("SELECT body FROM notes ORDER BY id", {})
        return {"notes": [r["body"] for r in rows]}

    async def run(principal, query, body):
        out = {}
        for name, sql in PROBES.items():
            try:
                rows = await ctx.db.execute(sql, {})
                out[name] = "ok:" + str(rows[0] if rows else "")
            except Denied as error:
                out[name] = "refused:" + error.code
        return out

    async def outside(principal, query, body):
        try:
            await ctx.http.get("https://example.org/")
            return {"outside": "reached"}
        except Denied as error:
            return {"outside": "refused:" + error.code}

    ctx.route("POST", "notes", add, permission="plugin:probe.use")
    ctx.route("GET", "probe", run, permission="plugin:probe.use")
    ctx.route("GET", "outside", outside, permission="plugin:probe.use")
"""


def _write(pl: PlHarness) -> None:
    target = pl.root / "available" / "probe"
    (target / "probe_plugin").mkdir(parents=True)
    (target / "migrations").mkdir()
    (target / "plugin.toml").write_text(MANIFEST)
    (target / "probe_plugin" / "__init__.py").write_text(textwrap.dedent(CODE))
    (target / "migrations" / "0001_notes.sql").write_text(
        "CREATE TABLE notes (id serial PRIMARY KEY, author text NOT NULL, body text NOT NULL)"
    )


async def _csrf(client: httpx.AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("__Host-portalab_csrf") or ""}


async def _post(client: httpx.AsyncClient, url: str, **kwargs: Any) -> httpx.Response:
    return await client.post(url, headers=await _csrf(client), **kwargs)


async def test_a_confined_plugin_end_to_end(pl: PlHarness, client: httpx.AsyncClient) -> None:
    pl.module.config = replace(
        pl.module.config, statement_timeout_ms=800, hook_timeout_seconds=8.0, error_threshold=100
    )
    _write(pl)
    await login(client, "boss")
    installed = await _post(client, "/api/v1/admin/plugins/install", json={"package": "probe"})
    assert installed.status_code == 201, installed.text
    review = installed.json()["review"]
    assert review["runtime"] == "confined"
    assert [c["capability"] for c in review["requested_capabilities"]] == [
        "operations",
        "permissions",
        "storage",
    ]
    early = await _post(client, "/api/v1/admin/plugins/probe/enable")
    assert early.status_code == 403
    assert (await _post(client, "/api/v1/admin/plugins/probe/approve")).status_code == 200
    enabled = await _post(client, "/api/v1/admin/plugins/probe/enable")
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["state"] == "enabled"
    host = pl.module.runtime.hosts["probe"]
    assert host.state == "running" and host.confinement["seccomp"] is True

    await login(client, "ursula")
    forbidden = await client.get("/api/v1/plugins/probe/probe")
    assert forbidden.status_code == 403  # the plugin's permission is a permission like any other
    await login(client, "boss")
    added = await _post(client, "/api/v1/plugins/probe/notes", json={"text": "hello"})
    assert added.status_code == 200, added.text
    assert added.json() == {"notes": ["hello"]}

    response = await client.get("/api/v1/plugins/probe/probe")
    assert response.status_code == 200, response.text
    probed = response.json()
    role = pl.module.storage.role("probe")
    assert probed["who"] == f"ok:{{'who': '{role}'}}"
    for name in ("core_table", "set_config_role", "read_file"):
        assert probed[name] == "refused:denied_statement", (name, probed[name])
    for name in ("reset_role", "set_role", "copy"):
        assert probed[name] == "refused:denied_statement", (name, probed[name])
    assert probed["two_statements"].startswith("refused:")
    assert probed["sleep"] == "refused:timeout"
    assert probed["advisory"].startswith("ok:")
    async with pl.database.session() as session:  # the lock did not outlive the plugin's call
        assert await session.scalar(text("SELECT pg_try_advisory_lock(424242)")) is True
        await session.execute(text("SELECT pg_advisory_unlock(424242)"))

    outside = (await client.get("/api/v1/plugins/probe/outside")).json()
    assert outside == {"outside": "refused:denied"}  # network not granted
    async with pl.database.session() as session:
        kinds = set(
            (await session.execute(select(Attempt.kind).where(Attempt.plugin_key == "probe"))).scalars()
        )
    assert {"denied_statement", "denied_capability", "timeout"} <= kinds

    disabled = await _post(client, "/api/v1/admin/plugins/probe/disable", json={})
    assert disabled.status_code == 200, disabled.text
    assert "probe" not in pl.module.runtime.hosts
