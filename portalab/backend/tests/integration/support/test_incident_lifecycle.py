"""016 T005/T008 — schema (append-only timeline, unique (source, dedup_key), FKs only to identity.users);
lifecycle investigating → identified → monitoring → resolved with an append-only timeline; resolve is
independent of any ticket; severity changes audited (critical sensitive); duplicate create returns the
existing incident; version conflicts; events per update."""

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from tests.authz_fixtures import make_admin
from tests.integration.identity.helpers import create_user, login, module_of
from tests.integration.support.conftest import SupportHarness

pytestmark = pytest.mark.integration


async def test_schema(support: SupportHarness) -> None:
    async with support.full.database.session() as session:
        tables = set(
            (
                await session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'support'"))
            ).scalars()
        )
        foreign = set(
            (
                await session.execute(
                    text(
                        "SELECT confrelid::regclass::text FROM pg_constraint c JOIN pg_namespace n "
                        "ON n.oid = c.connamespace WHERE n.nspname = 'support' AND contype = 'f'"
                    )
                )
            ).scalars()
        )
    assert {"incidents", "incident_services", "incident_updates", "incident_evidence"} <= tables
    assert all(f == "identity.users" or f.startswith("support.") for f in foreign)  # intra-module or users


async def staff(app: FastAPI, client: httpx.AsyncClient, support: SupportHarness) -> None:
    boss = await create_user(module_of(app), "boss")
    await make_admin(support.full, boss)
    await login(client, "boss")


async def test_lifecycle(app: FastAPI, client: httpx.AsyncClient, support: SupportHarness) -> None:
    await staff(app, client, support)
    created = (
        await client.post(
            "/api/v1/admin/incidents",
            json={
                "title": "Media streaming down",
                "severity": "major",
                "summary": "Playback fails.",
                "service_ids": ["s1"],
            },
        )
    ).json()
    incident, version = created["id"], created["version"]
    assert created["reference"] == "INC-0001" and created["state"] == "investigating"
    for state, message in (("identified", "Disk full."), ("monitoring", "Space freed.")):
        response = await client.post(
            f"/api/v1/admin/incidents/{incident}/updates",
            json={"state": state, "message": message},
            headers={"If-Match": str(version)},
        )
        assert response.status_code == 200, response.text
        version = response.json()["version"]
    stale = await client.post(
        f"/api/v1/admin/incidents/{incident}/updates", json={"message": "x"}, headers={"If-Match": "1"}
    )
    assert stale.status_code == 409 and stale.json()["code"] == "incident.version_conflict"
    raised = (await client.patch(f"/api/v1/admin/incidents/{incident}", json={"severity": "critical"})).json()
    assert raised["severity"] == "critical"
    resolved = (
        await client.post(f"/api/v1/admin/incidents/{incident}/resolve", json={"message": "Fixed."})
    ).json()
    assert resolved["state"] == "resolved" and resolved["resolved_at"]
    timeline = [(u["seq"], u["state"], u["severity"]) for u in resolved["updates"]]
    assert timeline == [
        (1, "investigating", "major"),
        (2, "identified", "major"),
        (3, "monitoring", "major"),
        (4, "monitoring", "critical"),
        (5, "resolved", "critical"),
    ]
    closed = await client.post(f"/api/v1/admin/incidents/{incident}/updates", json={"message": "late"})
    assert closed.status_code == 409 and closed.json()["code"] == "incident.resolved"
    async with support.full.database.session() as session:
        with pytest.raises(Exception, match="append-only"):
            await session.execute(text("UPDATE support.incident_updates SET message = 'tampered'"))
    async with support.full.database.session() as session:
        events = (
            (
                await session.execute(
                    text(
                        "SELECT type FROM core.event_outbox WHERE type LIKE 'incident.%' "
                        "ORDER BY received_at, type"
                    )
                )
            )
            .scalars()
            .all()
        )
        audits = (
            (
                await session.execute(
                    text(
                        "SELECT action FROM audit.audit_entries WHERE action LIKE 'incident.%' "
                        "ORDER BY occurred_at"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert events.count("incident.created") == 1 and events.count("incident.resolved") == 1
    assert events.count("incident.updated") == 3
    assert {"incident.created", "incident.updated", "incident.changed", "incident.resolved"} <= set(audits)


async def test_duplicates_and_validation(
    app: FastAPI, client: httpx.AsyncClient, support: SupportHarness
) -> None:
    port = support.module.port
    first = await port.create(
        title="Probe failing",
        source="health",
        severity="warning",
        evidence={"service_id": "s2"},
        dedup_key="s2:down",
    )
    again = await port.create(
        title="Probe failing",
        source="health",
        severity="warning",
        evidence={"service_id": "s2"},
        dedup_key="s2:down",
    )
    assert first.id == again.id and first.extra["severity"] == "major"
    await staff(app, client, support)
    bad = await client.post("/api/v1/admin/incidents", json={"title": "x", "severity": "apocalyptic"})
    assert bad.status_code == 422
