"""019 T019/T021 — any ``automatable`` event type triggers through the same model (with a field filter);
schedules fire once per due time through the same Gate; relative triggers fire at the event's reference
time plus the offset; a failing (e.g. plugin) action is isolated from other automations."""

from datetime import timedelta

import pytest

from portalab.capabilities.automation_actions import ActionType
from tests.integration.automations.conftest import AutoHarness, Recorder, basic

pytestmark = pytest.mark.integration


async def test_event_filters_and_isolation(au: AutoHarness) -> None:
    broken = Recorder(fail=True)
    au.actions.register(
        ActionType("plugin:demo.act", "plugin", "users.self.manage", "x", broken, "plugin:demo")
    )
    other = await au.automation(
        "other",
        basic(
            trigger={
                "kind": "event",
                "event_type": "test.other",
                "filter": [{"field": "label", "op": "eq", "value": "yes"}],
            },
            conditions=None,
        ),
    )
    failing = await au.automation(
        "failing", basic(steps=[{"id": "p", "action": "plugin:demo.act"}], conditions=None)
    )
    healthy = await au.automation("healthy", basic(conditions=None))
    await au.emit({"label": "yes"}, event_type="test.other")
    await au.emit({"label": "no"}, event_type="test.other")
    await au.emit({"value": 1})
    assert [e.status for e in await au.executions(other)] == ["success"]
    assert [e.status for e in await au.executions(failing)] == ["failed"]
    assert [e.status for e in await au.executions(healthy)] == ["success"]


PLAIN = [{"id": "record", "action": "test.record", "params": {"text": "tick ${automation.key}"}}]


async def test_schedules_and_relative(au: AutoHarness) -> None:
    start = au.clock.now()
    at = await au.automation(
        "once",
        basic(
            trigger={"kind": "at", "at": (start + timedelta(hours=2)).isoformat()},
            conditions=None,
            steps=PLAIN,
        ),
    )
    weekly = await au.automation(
        "weekly",
        basic(
            trigger={
                "kind": "recurring",
                "schedule": {"frequency": "daily", "time": "09:00"},
                "timezone": "UTC",
            },
            conditions=None,
            steps=PLAIN,
        ),
    )
    relative = await au.automation(
        "reminder",
        basic(
            trigger={
                "kind": "relative",
                "event_type": "test.happened",
                "reference": "starts_at",
                "offset_minutes": -60,
            },
            conditions=None,
        ),
    )
    await au.module.scheduler.run()
    await au.emit({"value": 1, "starts_at": (start + timedelta(hours=5)).isoformat()})
    for hours in (1, 2, 3, 4, 5, 22, 46):
        au.clock.set(start + timedelta(hours=hours))
        await au.module.scheduler.run()
        await au.module.scheduler.run()  # repeated runs never double-fire
    assert [e.trigger_ref["type"] for e in await au.executions(at)] == ["schedule"]
    assert len(await au.executions(weekly)) == 2  # Oct 2 and Oct 3 at 09:00 UTC
    [fired] = await au.executions(relative)
    assert fired.trigger_ref["type"] == "relative" and fired.status == "success"
