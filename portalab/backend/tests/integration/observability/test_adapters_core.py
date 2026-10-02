"""025 T014 — consumer lag/dead letters ⇒ events component; a reachable service whose sync fails is
functionally failing while its 006 state stays Operational; suspended automations are visible with their
reason; job queue and database components."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import text

from portalab.capabilities.events import Consumer, ConsumerContext, Envelope, EventType
from portalab.capabilities.observability import AUTOMATION_STATUS, AutomationStatus
from portalab.core.jobs.queue import enqueue
from portalab.core.time import FixedClock
from portalab.modules.health.models import ServiceState
from tests.observability_fixtures import ObsHarness


async def _evaluate(ob: ObsHarness) -> dict[str, object]:
    return {e.component: e for e in await ob.module.evaluator.evaluate_all()}


async def test_sync_failing_while_service_operational(ob: ObsHarness, clock: FixedClock) -> None:
    hl = ob.hl
    service_id = await hl.service()
    await hl.module.runner.probe(service_id)
    hl.cn.remote.put("a", at=1)
    hl.cn.remote.fail_after = 0
    await hl.cn.module.runner.run(UUID(service_id), kind="manual")  # the sync fails, the probe succeeds
    async with ob.database.session() as session:
        assert (await session.get(ServiceState, service_id)).state == "operational"  # type: ignore[union-attr]
    evaluations = await _evaluate(ob)
    connector = evaluations[f"connector:{service_id}"]
    assert connector.technical == "ok" and connector.functional == "failing"  # type: ignore[attr-defined]
    assert "sync_error" in connector.reason["functional"][0]["reason"]  # type: ignore[attr-defined]
    assert evaluations[f"sync:{service_id}"].functional == "failing"  # type: ignore[attr-defined]

    hl.cn.remote.fail_after = None
    await hl.cn.module.runner.run(UUID(service_id), kind="manual")
    clock.advance(timedelta(hours=ob.module.config.sync_stale_hours + 1))
    await hl.module.runner.probe(service_id)
    stale = (await _evaluate(ob))[f"connector:{service_id}"]
    assert stale.functional == "degraded" and "stale" in stale.reason["functional"][0]["reason"]  # type: ignore[attr-defined]


async def test_events_lag_and_dead_letters(ob: ObsHarness, clock: FixedClock) -> None:
    ob.events.event_types.register(EventType("obstest.happened", "obstest"))

    async def failing(event: Envelope, ctx: ConsumerContext) -> None:
        raise RuntimeError("consumer bug")

    ob.events.consumers.register(
        Consumer("obstest-failing", frozenset({"obstest.happened"}), failing, "obstest")
    )
    try:
        async with ob.database.unit_of_work() as uow:
            await ob.events.publisher.publish(uow.session, "obstest.happened", {}, occurred_at=clock.now())
        for _ in range(ob.events.config.max_delivery_attempts + 2):
            clock.advance(timedelta(hours=1))
            await ob.events.dispatcher.run_once()
        events = (await _evaluate(ob))["events"]
        facts = events.reason["functional"][0]["facts"]  # type: ignore[attr-defined]
        assert events.technical == "ok" and events.functional == "degraded"  # type: ignore[attr-defined]
        assert facts["dead_letters"] == 1
    finally:
        ob.events.consumers.unregister("obstest")
        ob.events.event_types.unregister("obstest")


async def test_automations_jobs_and_database(ob: ObsHarness, clock: FixedClock) -> None:
    class Automations:
        async def status(self) -> AutomationStatus:
            return AutomationStatus(3, 40, 1, suspended=({"rule_id": "r7", "reason": "loop protection"},))

    ob.hl.cn.full.identity.capabilities.provide(
        AUTOMATION_STATUS, Automations(), instance_ref="test", owner="test"
    )
    async with ob.database.unit_of_work() as uow:
        await enqueue(
            uow.session, kind="never.handled", dedup_key="obs-test-1", run_at=clock.now() - timedelta(hours=1)
        )
    evaluations = await _evaluate(ob)
    automations = evaluations["automations"]
    assert (
        automations.functional == "degraded"
        and "loop protection" in automations.reason["functional"][0]["reason"]
    )  # type: ignore[attr-defined]
    jobs = evaluations["jobs"]
    assert jobs.functional == "failing" and "worker" in jobs.reason["functional"][0]["reason"]  # type: ignore[attr-defined]
    assert evaluations["db"].technical == "ok"  # type: ignore[attr-defined]
    async with ob.database.session() as session:
        await session.execute(text("SELECT 1"))
    portal = (await _evaluate(ob))["portal"]
    assert portal.functional == "degraded"  # type: ignore[attr-defined]
