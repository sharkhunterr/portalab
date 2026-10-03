"""023 T012 — install (review/consent record) → enable → disable → archive; transitions emit ``plugin.*``
and ``plugin.state_changed`` once; invalid transitions refused; compatibility enforced on enable; schema
and role provisioned; the first code load needs a restart; transitions audited and permissioned."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.integration.identity.helpers import login
from tests.integration.plugins.conftest import PlHarness

pytestmark = pytest.mark.integration


async def test_lifecycle_through_the_api(pl: PlHarness, client: AsyncClient) -> None:
    pl.hello()
    await login(client, "ursula")
    assert (await client.post("/api/v1/admin/plugins/install", json={"package": "hello"})).status_code == 403
    await login(client, "boss")
    installed = await client.post("/api/v1/admin/plugins/install", json={"package": "hello"})
    assert installed.status_code == 201, installed.text
    review = installed.json()["review"]
    assert review["permissions"] == ["plugin:hello.view"] and review["code"] is True
    assert review["events"]["produces"] == ["plugin.hello.greeted"] and len(review["sha256"]) == 64
    assert "page" in review["extension_points"] and review["schema"] == "plugin_hello"
    early = await client.post("/api/v1/admin/plugins/hello/enable")
    assert early.status_code == 403 and early.json()["code"] == "plugin.review_required"
    assert (await client.post("/api/v1/admin/plugins/hello/approve")).json()["approved"] is True
    enabled = (await client.post("/api/v1/admin/plugins/hello/enable")).json()
    assert enabled["state"] == "enabled" and enabled["needs_restart"] is True  # code waits for a restart
    assert pl.registries.navigation.unregister("plugin:x") == 0
    diagnostics = (await client.get("/api/v1/admin/plugins/hello/diagnostics")).json()
    points = {c["point"] for c in diagnostics["contributions"]}
    assert {"nav", "page", "widget", "permission", "setting", "event_type", "i18n"} <= points
    assert "route" not in points  # code contributions arrive with the restart

    await pl.module.lifecycle.load_enabled()  # the restart
    detail = (await client.get("/api/v1/admin/plugins/hello")).json()
    assert detail["plugin"]["needs_restart"] is False
    points = {
        c["point"]
        for c in (await client.get("/api/v1/admin/plugins/hello/diagnostics")).json()["contributions"]
    }
    assert {
        "route",
        "search",
        "calendar",
        "ai_tool",
        "automation_action",
        "connector",
        "capability",
    } <= points
    assert (await client.post("/api/v1/admin/plugins/hello/archive")).status_code == 409  # disable first
    assert (await client.post("/api/v1/admin/plugins/hello/disable", json={})).json() == {
        "disabled": ["hello"]
    }
    assert (await client.post("/api/v1/admin/plugins/hello/disable", json={})).status_code == 409
    assert (await client.post("/api/v1/admin/plugins/hello/archive")).json()["state"] == "archived"
    assert (await client.post("/api/v1/admin/plugins/hello/enable")).status_code == 409

    async with pl.database.session() as session:
        schema = await session.scalar(
            text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'plugin_hello'")
        )
        greetings = await session.scalar(text("SELECT count(*) FROM plugin_hello.greetings"))
        changes = (
            await session.execute(
                text(
                    "SELECT payload->>'state', payload->>'seq' FROM events.events "
                    "WHERE type = 'plugin.state_changed' ORDER BY seq"
                )
            )
        ).all()
        audits = (
            (
                await session.execute(
                    text("SELECT action FROM audit.audit_entries WHERE action LIKE 'plugin.%' ORDER BY seq")
                )
            )
            .scalars()
            .all()
        )
    assert schema == 1 and greetings == 0  # data kept after archive
    assert [c[0] for c in changes] == ["installed", "enabled", "disabled", "disabled"]
    assert len({c[1] for c in changes}) == len(changes)
    assert audits == [
        "plugin.installed",
        "plugin.approved",
        "plugin.enabled",
        "plugin.disabled",
        "plugin.archived",
    ]
