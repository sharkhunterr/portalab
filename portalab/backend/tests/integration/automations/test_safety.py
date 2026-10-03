"""019 T024/T025 — safety: an A → B → A cycle is prevented; chains stop at ``maxChainDepth``; the
``automation.trigger`` action obeys the same limits; a ``dedup_key`` fires once per window; cooldown
honored; action and execution timeouts abort with ``timeout``; storms are batched or throttled and
recorded; other automations are unaffected."""

from dataclasses import replace

import pytest

from portalab.capabilities.automation_actions import ActionType
from tests.integration.automations.conftest import AutoHarness, Recorder, basic

pytestmark = pytest.mark.integration


def chain(me: str, target: str) -> dict[str, object]:
    return {
        "name": f"{me} triggers {target}",
        "trigger": {
            "kind": "event",
            "event_type": "automation.triggered",
            "filter": [{"field": "automation", "op": "eq", "value": me}],
        },
        "steps": [{"id": "next", "action": "automation.trigger", "params": {"automation": target}}],
    }


async def test_loops_and_depth(au: AutoHarness) -> None:
    start = await au.automation(
        "start",
        basic(
            conditions=None,
            steps=[{"id": "go", "action": "automation.trigger", "params": {"automation": "alpha"}}],
        ),
    )
    a = await au.automation("alpha", chain("alpha", "bravo"))
    b = await au.automation("bravo", chain("bravo", "alpha"))
    await au.emit({"value": 1})
    statuses = {
        "start": [e.status for e in await au.executions(start)],
        "a": [(e.status, e.error_code, e.depth) for e in await au.executions(a)],
        "b": [(e.status, e.error_code, e.depth) for e in await au.executions(b)],
    }
    assert statuses["start"] == ["success"]
    assert statuses["a"][0] == ("success", None, 1) and statuses["b"][0] == ("success", None, 2)
    assert statuses["a"][1][0] == "prevented" and statuses["a"][1][1] in ("loop", "depth")
    executions = [*await au.executions(start), *await au.executions(a), *await au.executions(b)]
    assert len({e.chain_id for e in executions}) == 1  # one chain, carried by the events' correlation id


async def test_dedup_cooldown_timeouts_and_storms(au: AutoHarness) -> None:
    dedup = await au.automation(
        "dedup", basic(conditions=None, limits={"dedup_key": "${event.label}", "dedup_window_s": 3600})
    )
    cool = await au.automation("cool", basic(conditions=None, limits={"cooldown_s": 600}))
    for label in ("x", "x", "y"):
        await au.emit({"value": 1, "label": label})
    assert [(e.status, e.error_code) for e in await au.executions(dedup)] == [
        ("success", None),
        ("prevented", "dedup"),
        ("success", None),
    ]
    assert [e.error_code for e in await au.executions(cool)] == [None, "cooldown", "cooldown"]
    slow = Recorder(delay=0.5)
    au.actions.register(ActionType("test.slow", "slow", "users.self.manage", "x", slow, "module:test"))
    au.module.config = replace(au.module.config, action_timeout_seconds=0.1)  # type: ignore[arg-type]
    timed = await au.automation("timed", basic(conditions=None, steps=[{"id": "s", "action": "test.slow"}]))
    await au.emit({"value": 1, "label": "z"})
    assert [(e.status, e.error_code) for e in await au.executions(timed)] == [("timeout", "action_timeout")]
    au.module.config = replace(au.module.config, action_timeout_seconds=10)
    throttled = await au.automation("throttled", basic(conditions=None, limits={"rate_per_min": 2}))
    batched = await au.automation(
        "batched", basic(conditions=None, limits={"rate_per_min": 2, "batchable": True})
    )
    for index in range(5):
        await au.emit({"value": 1, "label": f"storm{index}"})
    assert [e.status for e in await au.executions(throttled)] == [
        "success",
        "success",
        "throttled",
        "throttled",
        "throttled",
    ]
    rows = await au.executions(batched)
    assert len(rows) == 2 and rows[-1].batch_count == 4  # 2 executions, the last absorbing 3 more triggers
