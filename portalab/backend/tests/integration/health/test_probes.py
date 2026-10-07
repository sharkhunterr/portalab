"""006 T008 — probes write samples; an outage becomes Unavailable once (one event); recovery is
Operational; services are isolated; a monitor that stops reporting turns Unknown, never Operational."""

from datetime import timedelta

from sqlalchemy import func, select, text

from portalab.connectors.fake import BACKENDS, FakeBackend
from portalab.core.time import FixedClock
from portalab.modules.health.models import HealthSample, RecentError, ServiceState
from tests.health_fixtures import HealthHarness

STEP = timedelta(seconds=60)


async def _state(hl: HealthHarness, service_id: str) -> str:
    async with hl.cn.full.database.session() as session:
        row = await session.get(ServiceState, service_id)
    assert row is not None
    return row.state


async def test_outage_recovery_and_isolation(hl: HealthHarness, clock: FixedClock) -> None:
    other_url = hl.cn.base_url.replace("fake-", "other-")
    BACKENDS[other_url] = FakeBackend()
    failing = await hl.service("Failing")
    healthy = await hl.service("Healthy", base_url=other_url)
    runner = hl.module.runner

    assert await runner.probe(failing) is True
    await runner.probe(healthy)
    assert await _state(hl, failing) == "operational"

    hl.cn.remote.mode = "error"
    for _ in range(4):
        clock.advance(STEP)
        assert await runner.probe(failing) is False
        await runner.probe(healthy)
    assert await _state(hl, failing) == "unavailable"
    assert await _state(hl, healthy) == "operational"  # isolated

    hl.cn.remote.mode = "ok"
    clock.advance(STEP)
    await runner.probe(failing)
    assert await _state(hl, failing) == "operational"

    changes = [
        (e["to_state"], e["service_id"])
        for e in await hl.outbox("service.status_changed")
        if e.get("dimension") == "health"
    ]
    assert changes.count(("unavailable", failing)) == 1  # one event per transition
    assert [s for s, sid in changes if sid == failing] == [
        "operational",
        "degraded",
        "unavailable",
        "operational",
    ]
    async with hl.cn.full.database.session() as session:
        assert await session.scalar(select(func.count()).select_from(HealthSample)) == 11
        error = (await session.execute(select(RecentError))).scalar_one()
    assert error.code == "unreachable" and error.count == 4 and "cannot be reached" in error.message


async def test_stale_monitoring_is_unknown(hl: HealthHarness, clock: FixedClock) -> None:
    service_id = await hl.service()
    await hl.module.runner.probe(service_id)
    assert await _state(hl, service_id) == "operational"
    clock.advance(timedelta(seconds=hl.module.config.stale_after_seconds + 1))
    await hl.module.state.evaluate(service_id)  # no new probe arrived
    assert await _state(hl, service_id) == "unknown"


async def test_sweep_enqueues_probes_and_derives_unprobed(hl: HealthHarness) -> None:
    service_id = await hl.service()
    configured = str(await hl.cn.configure("Not enabled"))
    assert await hl.module.scheduler.sweep() == 1
    assert await hl.module.scheduler.sweep() == 1  # same slot: deduplicated job
    async with hl.cn.full.database.session() as session:
        jobs = (
            (await session.execute(text("SELECT payload FROM core.job WHERE kind = 'health.probe_service'")))
            .scalars()
            .all()
        )
    assert jobs == [{"service_id": service_id}]
    await hl.module.scheduler.handle(jobs[0])
    assert await _state(hl, service_id) == "operational"
    assert await _state(hl, configured) == "unknown"


async def test_capability_read_model(hl: HealthHarness) -> None:
    service_id = await hl.service()
    await hl.module.runner.probe(service_id)
    view = await hl.module.reader.get(service_id)
    assert view is not None and view.state == "operational" and view.availability == 1.0
    assert view.as_of is not None


async def test_lasting_outage_is_announced_once_per_milestone(hl: HealthHarness, clock: FixedClock) -> None:
    """027: a service still unavailable after 5, 10… minutes is announced once per milestone, with the
    failed probes so far — what « declare an incident after 10 minutes down » automations act on."""
    service_id = await hl.service("Plex")
    runner = hl.module.runner
    await runner.probe(service_id)
    hl.cn.remote.mode = "error"
    for _ in range(8):  # one probe a minute: unavailable within three failures, then a few more minutes
        clock.advance(STEP)
        await runner.probe(service_id)
    await hl.module.state.evaluate(service_id)  # a sweep in between changes nothing
    lasting = await hl.outbox("service.outage_lasting")
    assert [(e["minutes"], e["service_label"]) for e in lasting] == [(5, "Plex")]
    clock.advance(timedelta(minutes=6))
    await runner.probe(service_id)
    lasting = await hl.outbox("service.outage_lasting")
    assert [e["minutes"] for e in lasting] == [5, 10]
    assert lasting[-1]["failures"] == 9 and lasting[-1]["service_id"] == service_id  # probes failed so far
