"""006 T021 — detail sections are independent: a failing or slow section reports its own state while the
others render; Service State, Incident, Maintenance, Ticket and Sync State stay distinct elements."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from portalab.capabilities.health import INCIDENTS, IncidentRef
from portalab.core.time import FixedClock
from portalab.modules.health.detail.assembler import Tier
from tests.health_fixtures import HealthHarness


class _Incidents:
    def __init__(self) -> None:
        self.linked: list[tuple[str, str]] = []

    async def open_for_service(self, service_id: str) -> list[IncidentRef]:
        return [IncidentRef("inc-1", "Disk failure", "investigating", datetime(2026, 10, 1, tzinfo=UTC))]

    async def link(self, service_id: str, incident_id: str) -> None:
        self.linked.append((service_id, incident_id))

    async def create(self, *, title: str, source: str, severity: str, evidence: Any) -> IncidentRef:
        raise NotImplementedError

    async def attach(self, incident_id: str, evidence: Any) -> IncidentRef | None:
        return None


async def test_sections_are_independent_and_distinct(hl: HealthHarness, clock: FixedClock) -> None:
    service_id = await hl.service()
    await hl.module.runner.probe(service_id)
    await hl.cn.module.runner.run(
        hl.cn.module.manager.connector("fake") and __import__("uuid").UUID(service_id)
    )
    await hl.module.maintenance.create(
        hl.cn.admin,
        service_id=service_id,
        title="Later",
        starts_at=clock.now() + timedelta(days=1),
        ends_at=clock.now() + timedelta(days=1, hours=1),
    )
    incidents = _Incidents()
    hl.cn.full.identity.capabilities.provide(INCIDENTS, incidents, instance_ref="support", owner="test")

    async def slow(service_id: str, tier: Tier) -> Any:
        await asyncio.sleep(5)

    async def broken(service_id: str, tier: Tier) -> Any:
        raise RuntimeError("boom")

    hl.module.detail.overrides = {"history": slow, "availability": broken}
    detail = await hl.module.detail.detail(service_id, Tier(infrastructure=True, manage=True))
    sections = detail["sections"]
    assert sections["history"]["state"] == "unavailable" and "in time" in sections["history"]["detail"]
    assert sections["availability"]["state"] == "unavailable"
    assert sections["state"] == {
        "state": "available",
        "as_of": sections["state"]["as_of"],
        "data": sections["state"]["data"],
    }
    assert sections["state"]["data"]["state"] == "operational"
    assert sections["sync"]["data"]["status"] == "idle"  # sync state is its own section
    assert sections["maintenance"]["data"][0]["title"] == "Later"
    assert sections["incidents"]["data"][0]["id"] == "inc-1"
    assert sections["tickets"]["state"] == "no-data"  # Support tickets port not provided yet
    assert sections["infrastructure"]["state"] == "available"
    assert sections["operations"]["data"][0]["key"] == "restart"
    assert detail["service"]["name"] == "Fake"

    await hl.module.incidents.link(service_id, "inc-1")
    await hl.module.incidents.link(service_id, "inc-1")
    assert incidents.linked == [(service_id, "inc-1"), (service_id, "inc-1")]


async def test_incidents_section_without_support(hl: HealthHarness) -> None:
    service_id = await hl.service()
    detail = await hl.module.detail.detail(service_id, Tier())
    assert detail["sections"]["incidents"]["state"] == "no-data"
    assert set(detail["sections"]) == {"state", "availability", "maintenance", "incidents", "sync", "history"}
