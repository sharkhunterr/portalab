"""010 T019/T021/T024 — maintenance reminders J-1/H-1 are stored and sent at their time, superseded by a
reschedule (corrective message to people already told), never sent late (expired); a start alert; account
security events reach the user on the mandatory portal channel; replays and redeliveries produce nothing
new. Service outages are announced by Health itself (027: each service's alerting rule), not from here."""

from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text

from portalab.core.event_port import SubjectRef
from portalab.core.time import FixedClock
from tests.integration.identity.helpers import create_user, module_of
from tests.integration.notifications.conftest import NotifyHarness

pytestmark = pytest.mark.integration


async def titles(notify: NotifyHarness) -> list[str]:
    async with notify.database.session() as session:
        rows = await session.execute(
            text("SELECT c.template_key FROM notify.communications c ORDER BY c.created_at, c.id")
        )
        return [r[0].split(":", 1)[1] for r in rows]


async def reminders(notify: NotifyHarness) -> dict[tuple[int, str], str]:
    async with notify.database.session() as session:
        rows = await session.execute(
            text("SELECT schedule_version, kind, status, id FROM notify.maintenance_reminders")
        )
        return {(r[0], r[1]): r[2] for r in rows}


async def run_due(notify: NotifyHarness) -> list[str]:
    async with notify.database.session() as session:
        ids = (
            (
                await session.execute(
                    text(
                        "SELECT id FROM notify.maintenance_reminders"
                        " WHERE status = 'scheduled' ORDER BY run_at"
                    )
                )
            )
            .scalars()
            .all()
        )
    now = notify.module.clock.now()  # type: ignore[union-attr]
    out = []
    for reminder in ids:
        async with notify.database.session() as session:
            run_at = (
                await session.execute(
                    text("SELECT run_at FROM notify.maintenance_reminders WHERE id = :i"), {"i": reminder}
                )
            ).scalar_one()
        if run_at <= now:
            out.append(await notify.module.reminders.run({"reminder": str(reminder)}))
    return out


async def test_maintenance_reminders(
    app: FastAPI, client: httpx.AsyncClient, notify: NotifyHarness, clock: FixedClock
) -> None:
    await create_user(module_of(app), "alex")
    maintenance, service = str(uuid4()), str(uuid4())
    starts = clock.now() + timedelta(days=2)

    def payload(version: int, start: object) -> dict[str, object]:
        return {
            "maintenance_id": maintenance,
            "service_id": service,
            "schedule_version": version,
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(hours=2)).isoformat(),
        }  # type: ignore[attr-defined]

    await notify.publish("maintenance.scheduled", payload(1, starts), at=clock.now())
    await notify.dispatch()
    assert await reminders(notify) == {(1, "j1"): "scheduled", (1, "h1"): "scheduled"}
    clock.advance(timedelta(days=1, minutes=1))  # J-1 is due
    assert await run_due(notify) == ["sent"]
    later = starts + timedelta(days=1)
    await notify.publish("maintenance.rescheduled", payload(2, later), at=clock.now())
    await notify.dispatch()
    state = await reminders(notify)
    assert state[(1, "h1")] == "cancelled" and state[(2, "j1")] == "scheduled"
    assert await titles(notify) == ["maintenance.j1", "maintenance.rescheduled"]  # corrective to those told
    clock.set(later + timedelta(minutes=5))  # the worker was down: both v2 reminders are now late
    assert sorted(await run_due(notify)) == ["expired", "expired"]
    await notify.publish("maintenance.started", payload(2, later), at=clock.now())
    await notify.dispatch()
    assert (await titles(notify))[-1] == "maintenance.start"
    await notify.ev.module.dispatcher.run_once()
    assert len(await titles(notify)) == 3  # nothing more on redelivery


async def test_account_source_and_outages_left_to_health(
    app: FastAPI, notify: NotifyHarness, clock: FixedClock
) -> None:
    alex = await create_user(module_of(app), "alex")
    service = str(uuid4())
    change = {
        "service_id": service,
        "dimension": "health",
        "from_state": "available",
        "to_state": "unavailable",
        "state_seq": 4,
    }
    await notify.publish("service.status_changed", change, at=clock.now())
    await notify.publish("service.status_changed", {**change, "dimension": "maintenance"}, at=clock.now())
    await notify.publish("user.suspended", {}, at=clock.now(), subject=SubjectRef("user", str(alex)))
    await notify.dispatch()
    async with notify.database.session() as session:
        rows = (
            await session.execute(
                text("SELECT category, kind, priority FROM notify.communications ORDER BY category")
            )
        ).all()
        inbox = (
            (
                await session.execute(
                    text("SELECT category FROM notify.notifications WHERE user_id = :u ORDER BY category"),
                    {"u": alex},
                )
            )
            .scalars()
            .all()
        )
    assert [tuple(r) for r in rows] == [("account.security", "notification", "high")]
    assert inbox == ["account.security"]


async def test_a_member_hears_of_their_account_security_events(
    app: FastAPI, notify: NotifyHarness, clock: FixedClock
) -> None:
    """Issue 407: a password changed (by them or an administrator) and a single sign-on linked are told to
    the member, in their notification center (a change they did not make shows at once)."""
    alex = await create_user(module_of(app), "alex")
    subject = SubjectRef("user", str(alex))
    await notify.publish("user.password_changed", {"by": "admin"}, at=clock.now(), subject=subject)
    await notify.publish("user.sso_linked", {"provider": "sso.example.org"}, at=clock.now(), subject=subject)
    await notify.dispatch()
    async with notify.database.session() as session:
        titles = (
            (
                await session.execute(
                    text("SELECT title FROM notify.notifications WHERE user_id = :u ORDER BY title"),
                    {"u": alex},
                )
            )
            .scalars()
            .all()
        )
    assert titles == [
        "A single sign-on account now signs in as you",
        "An administrator set a new password for your account",
    ]
