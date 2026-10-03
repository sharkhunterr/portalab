"""019 T008 — WHEN → IF → THEN: an event fires, conditions are evaluated, the action runs, the execution is
``success`` with its trace and steps; false conditions record ``no_op``; a duplicate delivery runs once;
paused or archived automations ignore events; replays never re-run automations."""

import pytest

from portalab.capabilities.events import Envelope
from tests.integration.automations.conftest import AutoHarness, basic

pytestmark = pytest.mark.integration


async def test_event_condition_action(au: AutoHarness) -> None:
    automation = await au.automation("records", basic())
    await au.emit({"value": 3, "label": "go"})
    await au.emit({"value": 0, "label": "skip"})
    executions = await au.executions(automation)
    assert [e.status for e in executions] == ["success", "no_op"]
    first, skipped = executions
    assert first.conditions_trace == [{"leaf": "event_field", "result": True}]
    assert first.steps[0]["status"] == "ok" and first.steps[0]["result"] == {"recorded": 1}  # body not kept
    assert skipped.conditions_trace == [{"leaf": "event_field", "result": False}] and skipped.steps == []
    call = au.record.calls[0]
    assert call["params"] == {"text": f"value 3 by {au.people['ursula']}"}
    assert call["principal"].channel == "automation" and call["principal"].acting_for == au.people["boss"]
    assert first.principal["kind"] == "author" and first.trigger_ref["type"] == "test.happened"


async def test_duplicates_states_and_replays(au: AutoHarness) -> None:
    automation = await au.automation("records", basic())
    await au.emit({"value": 2})
    async with au.database.session() as session:
        from sqlalchemy import text

        row = (
            (await session.execute(text("SELECT * FROM events.events WHERE type = 'test.happened'")))
            .mappings()
            .one()
        )
    envelope = Envelope(
        event_id=row["event_id"],
        seq=row["seq"],
        type=row["type"],
        type_version=1,
        occurred_at=row["occurred_at"],
        received_at=row["received_at"],
        source_system="test",
        source_event_id=None,
        actor_user_id=au.people["ursula"],
        actor_kind="user",
        subject_type=None,
        subject_id=None,
        payload=row["payload"],
        provenance={},
        correlation_id=row["correlation_id"],
    )

    class Ctx:
        replay = False
        as_of = row["occurred_at"]

        async def idempotent_effect(self, key: str) -> bool:
            return True

    await au.module.triggers.handle(envelope, Ctx())  # redelivery
    replay = Ctx()
    replay.replay = True
    await au.module.triggers.handle(envelope, replay)
    assert len(au.record.calls) == 1 and len(await au.executions(automation)) == 1
    await au.module.definitions.transition(au.p("boss"), automation, "pause")
    await au.emit({"value": 5})
    await au.module.definitions.transition(au.p("boss"), automation, "archive")
    await au.emit({"value": 6})
    assert len(au.record.calls) == 1
