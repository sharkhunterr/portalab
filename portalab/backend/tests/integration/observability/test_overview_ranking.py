"""025 T026 — the overview ranks problems: action needed → impact → criticality → age → details; it is
not a flat metric list; the Control Center panel degrades on its own."""

from datetime import timedelta
from uuid import UUID

from portalab.capabilities.administration import PANEL_CAPABILITY
from portalab.core.time import FixedClock
from portalab.modules.observability.detectors.rules import Finding
from tests.observability_fixtures import ObsHarness


async def test_ranking(ob: ObsHarness, clock: FixedClock) -> None:
    service_id = await ob.hl.service()
    await ob.hl.module.runner.probe(service_id)
    ob.hl.cn.remote.fail_after = 0
    ob.hl.cn.remote.put("a", at=1)
    await ob.hl.cn.module.runner.run(UUID(service_id), kind="manual")  # connector failing (action needed)
    ob.hooks.error("jobs", "job_failed", RuntimeError("boom"))
    await ob.module.cycle()
    clock.advance(timedelta(minutes=5))
    await ob.module.escalation.observe([Finding("latency_spike", "portal:/x", "warning", "slow")])
    problems = await ob.module.overview.problems()
    kinds = [(p["kind"], p["action_needed"]) for p in problems]
    assert kinds[0][1] is True and all(a for _, a in kinds[: sum(a for _, a in kinds)])  # action-needed first
    needing = [p for p in problems if p["action_needed"]]
    assert [p["impact"] for p in needing] == sorted((p["impact"] for p in needing), reverse=True)
    assert {"component", "error", "anomaly"} <= {p["kind"] for p in problems}
    assert all("diagnostics" in p and "details" in p for p in problems)
    assert not any(p["kind"] == "metric" for p in problems)


async def test_panel_degrades_alone(ob: ObsHarness) -> None:
    [registration] = [
        r
        for r in ob.hl.cn.full.identity.capabilities.system_providers(PANEL_CAPABILITY)
        if r.instance_ref == "observability"
    ]

    async def broken(**_: object) -> list[object]:
        raise RuntimeError("store down")

    ob.module.overview.problems = broken  # type: ignore[method-assign]
    result = await registration.provider.panel(ob.hl.cn.admin)
    assert result.state == "unavailable"
