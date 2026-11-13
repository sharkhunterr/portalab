"""019 T028/T029 — dry-run evaluates conditions and plans steps with zero side effects; presets validate and
instantiate as drafts; a manual run needs a confirmation and obeys the safety controls."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from portalab.capabilities.automation_actions import ActionType
from tests.integration.automations.conftest import AutoHarness, Recorder, basic
from tests.integration.identity.helpers import login

pytestmark = pytest.mark.integration


async def test_dry_run_and_manual_run(au: AutoHarness, client: AsyncClient) -> None:
    wipe = Recorder()
    au.actions.register(
        ActionType("test.wipe", "wipe", "users.manage", "x", wipe, "module:test", sensitivity="destructive")
    )
    automation = await au.automation(
        "dry",
        basic(
            steps=[
                {"id": "r", "action": "test.record", "params": {"text": "${event.label}"}},
                {"id": "w", "action": "test.wipe"},
            ]
        ),
    )
    await login(client, "boss")
    plan = (
        await client.post(
            f"/api/v1/admin/automations/{automation}/dry-run",
            json={"payload": {"value": 2, "label": "sample"}},
        )
    ).json()
    assert plan["conditions_passed"] is True and plan["trace"] == [{"leaf": "event_field", "result": True}]
    assert [(s["action"], s["approval"], s["params"]) for s in plan["steps"]] == [
        ("test.record", False, {"text": "sample"}),
        ("test.wipe", True, {}),
    ]
    false_plan = (
        await client.post(f"/api/v1/admin/automations/{automation}/dry-run", json={"payload": {"value": 0}})
    ).json()
    assert false_plan["conditions_passed"] is False and false_plan["steps"] == []
    async with au.database.session() as session:
        assert await session.scalar(text("SELECT count(*) FROM automations.executions")) == 0
    assert au.record.calls == [] and wipe.calls == []
    first = await client.post(f"/api/v1/admin/automations/{automation}/run", json={})
    assert first.status_code == 409
    ran = await client.post(
        f"/api/v1/admin/automations/{automation}/run", json={"confirmation": first.json()["confirmation"]}
    )
    assert ran.json()["status"] in ("no_op", "awaiting_approval")  # no event: the event_field leaf is unknown


async def test_templates(au: AutoHarness, client: AsyncClient) -> None:
    await login(client, "boss")
    templates = {t["key"]: t for t in (await client.get("/api/v1/admin/automations/templates")).json()}
    assert set(templates) == {
        "campaign-start-announcement",
        "campaign-ending-soon",
        "welcome-on-verification",
        "critical-service-incident-draft",
        "weekly-community-digest-news",
        "new-ticket-notify-support",
        "service-down-10-minutes-incident",  # 027: an incident when a service stays down
        "parity-check-banner",  # issue 122: a banner while a server checks its parity
        "parity-check-banner-end",
        "service-down-banner",  # issue 394: the degraded banner is an automation, no longer built in
        "service-back-banner-end",
    }
    # the harness registers no owner actions/events beyond tests: templates report what is missing
    assert all(not t["valid"] for t in templates.values())
    missing = await client.post("/api/v1/admin/automations/templates/nope/instantiate", json={"key": "nope"})
    assert missing.status_code == 404
