"""007 T030/T034 — events routes protected (anonymous 401, plain user 403 on admin routes); metrics carry
no payload values or user ids."""

import httpx
import pytest
from fastapi import FastAPI

from portalab.capabilities.events import EventType
from portalab.modules.events.observability import metrics
from tests.events_fixtures import EventsHarness
from tests.integration.identity.helpers import create_user, login, module_of

pytestmark = pytest.mark.integration
ADMIN_ROUTES = [
    ("GET", "/api/v1/admin/events"),
    ("GET", "/api/v1/admin/events/deliveries"),
    ("GET", "/api/v1/admin/events/quarantine"),
    ("POST", "/api/v1/admin/events/quarantine/00000000-0000-7000-8000-000000000000/discard"),
    ("POST", "/api/v1/admin/replay"),
]


async def test_matrix(app: FastAPI, client: httpx.AsyncClient, ev: EventsHarness) -> None:
    app.state.events_module = ev.module
    for method, path in [*ADMIN_ROUTES, ("GET", "/api/v1/me/history")]:
        assert (await client.request(method, path, json={})).status_code == 401, path
    await create_user(module_of(app), "plain")
    await login(client, "plain")
    for method, path in ADMIN_ROUTES:
        assert (await client.request(method, path, json={"projection": "x"})).status_code == 403, path
    assert (await client.get("/api/v1/me/history")).status_code == 200


async def test_metrics_hold_no_values(ev: EventsHarness) -> None:
    from datetime import UTC, datetime

    metrics.reset()
    ev.types.register(EventType("demo.happened", "t"))
    async with ev.full.database.unit_of_work() as uow:
        await ev.publisher.publish(
            uow.session,
            "demo.happened",
            {"note_ref": "SECRET-REF"},
            occurred_at=datetime(2026, 10, 1, tzinfo=UTC),
        )
        await ev.publisher.publish(
            uow.session, "unknown.type", {}, occurred_at=datetime(2026, 10, 1, tzinfo=UTC)
        )
    snapshot = metrics.snapshot()
    assert snapshot["events.ingestion.accepted"] == 1
    assert snapshot["events.ingestion.quarantined.unknown_type"] == 1
    assert "SECRET-REF" not in " ".join(snapshot)
