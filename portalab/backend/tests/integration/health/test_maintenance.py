"""006 T015 — maintenance windows: schedule/reschedule/cancel; flips to Maintenance and back at absolute
instants; missed transitions reconciled; events carry ``schedule_version``; reference time zone stored."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import text

from portalab.core.time import FixedClock
from portalab.modules.health.common import InvalidWindow
from portalab.modules.health.models import ServiceState
from tests.health_fixtures import HealthHarness


async def _state(hl: HealthHarness, service_id: str) -> str:
    async with hl.cn.full.database.session() as session:
        row = await session.get(ServiceState, service_id)
    return row.state if row else "none"


async def test_window_lifecycle(hl: HealthHarness, clock: FixedClock) -> None:
    service_id = await hl.service()
    await hl.module.runner.probe(service_id)
    now = clock.now()
    window = await hl.module.maintenance.create(
        hl.cn.admin,
        service_id=service_id,
        title="Disk upgrade",
        starts_at=now + timedelta(hours=1),
        ends_at=now + timedelta(hours=2),
        reference_time_zone="Europe/Paris",
    )
    assert window["status"] == "scheduled" and window["reference_time_zone"] == "Europe/Paris"
    async with hl.cn.full.database.session() as session:
        jobs = (
            await session.execute(
                text(
                    "SELECT kind, run_at FROM core.job WHERE kind LIKE 'health.maintenance_%' ORDER BY run_at"
                )
            )
        ).all()
    assert [(k, r) for k, r in jobs] == [
        ("health.maintenance_start", now + timedelta(hours=1)),
        ("health.maintenance_end", now + timedelta(hours=2)),
    ]
    moved = await hl.module.maintenance.reschedule(
        hl.cn.admin, UUID(window["id"]), ends_at=now + timedelta(hours=3)
    )
    assert moved["schedule_version"] == 2

    clock.advance(timedelta(hours=1, minutes=1))
    await hl.module.maintenance.handle_job({"maintenance_id": window["id"], "schedule_version": 1}, "started")
    # the stale v1 job is ignored, but the v2 start is due: a sweep/job reconciles it
    await hl.module.maintenance.handle_job({"maintenance_id": window["id"], "schedule_version": 2}, "started")
    assert await _state(hl, service_id) == "maintenance"
    hl.cn.remote.mode = "error"
    clock.advance(timedelta(minutes=1))
    await hl.module.runner.probe(service_id)
    clock.advance(timedelta(minutes=1))
    await hl.module.runner.probe(service_id)
    assert await _state(hl, service_id) == "maintenance"  # planned work is not an outage
    hl.cn.remote.mode = "ok"
    clock.set(now + timedelta(hours=3, minutes=1))
    await hl.module.runner.probe(service_id)
    await hl.module.maintenance.reconcile()
    assert await _state(hl, service_id) == "operational"

    events = await hl.outbox("maintenance.")
    assert [(e["type"], e["schedule_version"]) for e in events] == [
        ("maintenance.scheduled", 1),
        ("maintenance.rescheduled", 2),
        ("maintenance.started", 2),
        ("maintenance.ended", 2),
    ]


async def test_missed_window_reconciled_and_cancel(hl: HealthHarness, clock: FixedClock) -> None:
    service_id = await hl.service()
    now = clock.now()
    past = await hl.module.maintenance.create(
        hl.cn.admin,
        service_id=None,
        title="Missed",
        starts_at=now + timedelta(minutes=5),
        ends_at=now + timedelta(minutes=10),
    )
    clock.advance(timedelta(hours=1))  # the worker was down during the whole window
    transitions = await hl.module.maintenance.reconcile()
    assert transitions == [f"{past['id']}:started", f"{past['id']}:ended"]

    upcoming = await hl.module.maintenance.create(
        hl.cn.admin,
        service_id=service_id,
        title="Later",
        starts_at=clock.now() + timedelta(days=1),
        ends_at=clock.now() + timedelta(days=1, hours=1),
    )
    cancelled = await hl.module.maintenance.cancel(hl.cn.admin, UUID(upcoming["id"]))
    assert cancelled["status"] == "cancelled"
    assert await hl.module.maintenance.windows() == []
    async with hl.cn.full.database.session() as session:
        audited = await session.scalar(
            text("SELECT count(*) FROM audit.audit_entries WHERE action = 'maintenance.cancelled'")
        )
    assert audited == 1


async def test_invalid_windows(hl: HealthHarness) -> None:
    start = datetime(2026, 11, 1, 2, 0, tzinfo=UTC)
    with pytest.raises(InvalidWindow):
        await hl.module.maintenance.create(
            hl.cn.admin, service_id=None, title="x", starts_at=start, ends_at=start - timedelta(hours=1)
        )
    with pytest.raises(InvalidWindow):
        await hl.module.maintenance.create(
            hl.cn.admin,
            service_id=None,
            title="x",
            starts_at=start.replace(tzinfo=None),
            ends_at=start + timedelta(hours=1),
        )
    with pytest.raises(InvalidWindow):
        await hl.module.maintenance.create(
            hl.cn.admin,
            service_id=None,
            title="x",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            reference_time_zone="Mars/Olympus",
        )
