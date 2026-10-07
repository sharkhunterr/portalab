"""006 T008 — probes write samples; an outage becomes Unavailable once (one event); recovery is
Operational; services are isolated; a monitor that stops reporting turns Unknown, never Operational."""

from dataclasses import replace
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select, text

from portalab.capabilities.health import INCIDENTS
from portalab.capabilities.notifications import NOTIFY
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


class _Incidents:
    """The Support port as Health sees it (create is idempotent per dedup key; closing by source)."""

    def __init__(self) -> None:
        self.created: dict[str, dict[str, Any]] = {}
        self.closed: list[tuple[str, str]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.created.setdefault(kwargs["dedup_key"], kwargs)
        return None

    async def resolve_for_service(self, service_id: str, *, source: str, message: str) -> int:
        self.closed.append((service_id, source))
        return 1

    async def open_for_service(self, service_id: str) -> list[Any]:
        return []

    async def link(self, service_id: str, incident_id: str) -> None:
        return None

    async def attach(self, incident_id: str, evidence: Any) -> Any:
        return None

    async def get(self, incident_id: str) -> Any:
        return None


async def test_outage_becomes_an_incident_after_its_delay_and_closes_when_back(
    hl: HealthHarness, clock: FixedClock
) -> None:
    """027: no automation needed — a service unavailable for longer than its delay (10 min for a « major »
    service) gets one incident, with its importance's severity; it is closed when the service is back."""
    port = _Incidents()
    hl.cn.full.identity.capabilities.provide(INCIDENTS, port, instance_ref="support", owner="test:support")
    service_id = await hl.service("Plex")
    runner = hl.module.runner
    await runner.probe(service_id)
    hl.cn.remote.mode = "error"
    for _ in range(8):  # unavailable within three failures — not yet 10 minutes of outage
        clock.advance(STEP)
        await runner.probe(service_id)
    assert port.created == {}
    for _ in range(6):
        clock.advance(STEP)
        await runner.probe(service_id)
    assert len(port.created) == 1
    [incident] = port.created.values()
    assert incident["severity"] == "major" and incident["service_ids"] == [service_id]
    assert incident["source"] == "health" and "Plex" in incident["title"]

    hl.cn.remote.mode = "ok"
    clock.advance(STEP)
    await runner.probe(service_id)
    assert port.closed == [(service_id, "health")]


class _Notify:
    """The notification engine as Health sees it: the requests it was asked to send."""

    def __init__(self) -> None:
        self.sent: list[Any] = []

    async def send(self, request: Any) -> Any:
        self.sent.append(request)
        return None


async def test_outage_is_announced_by_its_rule_then_back(hl: HealthHarness, clock: FixedClock) -> None:
    """027: a « major » outage is told after 5 minutes to administrators and members (apart), by name —
    once — and its end too; nothing is told for a blip shorter than the delay."""
    notify = _Notify()
    hl.cn.full.identity.capabilities.provide(NOTIFY, notify, instance_ref="notify", owner="test:notify")
    service_id = await hl.service("Plex")
    runner = hl.module.runner
    await runner.probe(service_id)
    hl.cn.remote.mode = "error"
    for _ in range(6):  # unavailable after three failures: three minutes of outage so far
        clock.advance(STEP)
        await runner.probe(service_id)
    assert notify.sent == []
    for _ in range(3):
        clock.advance(STEP)
        await runner.probe(service_id)
    sent = [(r.audience.permission, r.audience.without, r.category, r.kind) for r in notify.sent]
    assert sent == [
        ("services.manage", None, "system.health", "alert"),
        ("services.read", "services.manage", "system.health", "alert"),
    ]
    assert notify.sent[0].params["service"] == "Plex" and notify.sent[0].params["minutes"] == 5
    assert notify.sent[0].template_key == "notifications:service.unavailable"

    hl.cn.remote.mode = "ok"
    clock.advance(STEP)
    await runner.probe(service_id)
    assert [r.template_key for r in notify.sent[2:]] == ["notifications:service.back"] * 2
    back = notify.sent[2]
    assert back.kind == "notification" and back.params["minutes"] >= 7  # how long it was down


async def test_alerting_rule_and_service_overrides(hl: HealthHarness, clock: FixedClock) -> None:
    """027: the administrator's rule for an importance applies (here: no incident, administrators told at
    once, by e-mail); a service's own overrides win field by field."""
    notify, port = _Notify(), _Incidents()
    capabilities = hl.cn.full.identity.capabilities
    capabilities.provide(NOTIFY, notify, instance_ref="notify", owner="test:notify")
    capabilities.provide(INCIDENTS, port, instance_ref="support", owner="test:support")
    rule = {"incident": False, "notify_after": 0, "notify_members": False, "email_admins": True}
    hl.module.config = replace(hl.module.config, alert_rules={"major": rule})
    service_id = await hl.service("Plex")
    info = await hl.module.state.service_info(service_id)
    assert info is not None
    effective = hl.module.state.rule(info)
    assert not effective.incident and effective.notify_after == 0 and effective.auto_resolve
    overridden = hl.module.state.rule(replace(info, alerting={"incident": True, "incident_after": 2}))
    assert overridden.incident and overridden.incident_after == 2 and overridden.email_admins

    runner = hl.module.runner
    await runner.probe(service_id)
    hl.cn.remote.mode = "error"
    for _ in range(15):
        clock.advance(STEP)
        await runner.probe(service_id)
    assert port.created == {}  # no incident for this importance
    assert [(r.audience.permission, r.category) for r in notify.sent] == [
        ("services.manage", "system.health_email")
    ]  # told as soon as it was down
