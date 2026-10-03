"""025 T023 — escalation policy (auto vs human validation); repeated anomalies with one fingerprint attach
to a single open incident through the ``support.incidents`` port; a down port keeps the anomaly
``pending_validation`` and retries; no local incident table."""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from portalab.capabilities.health import INCIDENTS, IncidentRef
from portalab.modules.observability.detectors.rules import Finding
from tests.observability_fixtures import ObsHarness


class Support:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.attached: list[str] = []
        self.down = False

    async def open_for_service(self, service_id: str) -> list[IncidentRef]:
        return []

    async def get(self, incident_id: str) -> IncidentRef | None:
        return None

    async def link(self, service_id: str, incident_id: str) -> None:
        return None

    async def create(self, *, title: str, source: str, severity: str, evidence: Any) -> IncidentRef:
        if self.down:
            raise ConnectionError("support unavailable")
        self.created.append({"title": title, "severity": severity})
        return IncidentRef(f"inc-{len(self.created)}", title, "open", datetime(2026, 10, 1, tzinfo=UTC))

    async def attach(self, incident_id: str, evidence: Any) -> IncidentRef | None:
        if self.down:
            raise ConnectionError("support unavailable")
        self.attached.append(incident_id)
        return IncidentRef(incident_id, "x", "open", datetime(2026, 10, 1, tzinfo=UTC))


CRITICAL = Finding("stuck_consumer", "events:rewards", "critical", "stuck", {"lag": 12})
WARNING = Finding("long_sync", "sync:s1", "warning", "long", {"latest_ms": 1})


async def test_auto_escalation_and_attach(ob: ObsHarness) -> None:
    support = Support()
    ob.hl.cn.full.identity.capabilities.provide(INCIDENTS, support, instance_ref="support", owner="test")
    ob.module.config = replace(
        ob.module.config, escalation_require_validation=False, escalation_auto_severity="critical"
    )
    await ob.module.escalation.observe([CRITICAL])
    assert support.created == [{"title": "stuck consumer on events:rewards", "severity": "critical"}]
    await ob.module.escalation.observe([CRITICAL])
    await ob.module.escalation.observe([CRITICAL])
    assert len(support.created) == 1 and support.attached == [
        "inc-1",
        "inc-1",
    ]  # one incident per fingerprint
    await ob.module.escalation.observe([WARNING])
    items = {a["detector"]: a for a in await ob.module.escalation.anomalies()}
    assert items["stuck_consumer"]["status"] == "escalated" and items["stuck_consumer"]["occurrences"] == 3
    assert items["long_sync"]["status"] == "pending_validation"  # below the auto severity: a human decides
    assert len(await ob.outbox("observability.anomaly_detected")) == 2


async def test_validation_and_port_down_retry(ob: ObsHarness) -> None:
    support = Support()
    support.down = True
    ob.hl.cn.full.identity.capabilities.provide(INCIDENTS, support, instance_ref="support", owner="test")
    [anomaly] = await ob.module.escalation.observe([WARNING])
    decided = await ob.module.escalation.decide(ob.hl.cn.admin, anomaly.id, "validate")
    assert decided.status == "pending_validation"  # Support is down: kept, not lost
    support.down = False
    assert await ob.module.escalation.retry_pending() == 1
    assert {a["status"] for a in await ob.module.escalation.anomalies()} == {"escalated"}
    [other] = await ob.module.escalation.observe([Finding("repeated_failure", "jobs:x", "warning", "again")])
    dismissed = await ob.module.escalation.decide(ob.hl.cn.admin, other.id, "dismiss")
    assert dismissed.status == "dismissed" and len(support.created) == 1
