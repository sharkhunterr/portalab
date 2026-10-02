"""020 T021 — the wizard validates base settings, creates the sole Admin through ``IdentityBootstrap``,
runs the
registered optional steps (skippable), then answers 410; reopening needs an explicit audited action."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from portalab.capabilities.administration import FIRST_RUN_STEP_CAPABILITY
from portalab.modules.authz.models import AuditEntry
from tests.integration.identity.helpers import PASSWORD, login
from tests.privacy_fixtures import FullPlatform


class ServicesStep:
    def __init__(self) -> None:
        self.payloads: list[Mapping[str, Any]] = []

    async def run(self, payload: Mapping[str, Any], admin_id: UUID) -> Mapping[str, Any]:
        self.payloads.append(payload)
        return {"connected": len(payload.get("services", []))}


async def test_wizard_once(app: FastAPI, client: httpx.AsyncClient, full: FullPlatform) -> None:
    step = ServicesStep()
    full.identity.capabilities.provide(
        FIRST_RUN_STEP_CAPABILITY,
        step,
        instance_ref="connectors.services",
        owner="test",
        metadata={"step": "services", "skippable": True},
    )
    status = (await client.get("/api/v1/admin/first-run")).json()
    assert status == {"completed": False, "steps": [{"step": "services", "skippable": True}]}
    invalid = await client.post(
        "/api/v1/admin/first-run",
        json={"login": "root", "password": PASSWORD, "settings": {"identity.dormancyDays": "soon"}},
    )
    assert invalid.status_code == 422  # nothing created
    done = await client.post(
        "/api/v1/admin/first-run",
        json={
            "login": "root",
            "password": PASSWORD,
            "display_name": "Root",
            "settings": {"identity.registrationMode": "open"},
            "steps": {"services": {"services": ["plex"]}},
        },
    )
    assert done.status_code == 201 and done.json()["steps"] == {"services": "done"}
    assert step.payloads == [{"services": ["plex"]}]
    assert (await full.administration.config.get("identity.registrationMode")).value == "open"
    again = await client.post("/api/v1/admin/first-run", json={"login": "evil", "password": PASSWORD})
    assert again.status_code == 410 and again.json()["code"] == "admin.first_run_completed"

    await login(client, "root")
    reopened = await client.post("/api/v1/admin/first-run/reopen", json={"reason": "add services"})
    assert reopened.status_code == 204
    anonymous = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://portal.test")
    async with anonymous:
        assert (
            await anonymous.post("/api/v1/admin/first-run", json={"login": "x", "password": PASSWORD})
        ).status_code == 401
    rerun = await client.post(
        "/api/v1/admin/first-run", json={"login": "ignored", "password": PASSWORD, "steps": {}}
    )
    assert rerun.status_code == 201 and rerun.json()["steps"] == {"services": "skipped"}
    async with full.database.session() as session:
        actions = (await session.execute(select(AuditEntry.action))).scalars().all()
    assert "admin.firstrun_reopened" in actions and actions.count("admin.firstrun_completed") == 2
