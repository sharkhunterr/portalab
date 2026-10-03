"""013 T015 — events become grants per rule version (fixed and per-unit), the three values recorded
separately with source, amount, rule version and time; duplicate and late deliveries never double-grant;
concurrent events for one user are serialized; ``reward.granted`` emitted; notifications sent after commit."""

import asyncio
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from portalab.capabilities.notifications import NOTIFY, CommunicationRef, CommunicationRequest
from portalab.core.authz_port import Principal
from portalab.modules.gamification.verify.verifier import verify
from tests.integration.gamification.conftest import GamHarness

pytestmark = pytest.mark.integration


class Outbox:
    def __init__(self) -> None:
        self.sent: list[CommunicationRequest] = []

    async def send(
        self, request: CommunicationRequest, *, caller: Principal | None = None
    ) -> CommunicationRef:
        self.sent.append(request)
        return CommunicationRef(uuid4(), True, 1)


async def test_events_grant_once(gm: GamHarness) -> None:
    outbox = Outbox()
    gm.ev.full.identity.capabilities.provide(NOTIFY, outbox, instance_ref="t", owner="test")
    await gm.rule(
        "listen",
        {
            "event_type": "media.played",
            "predicate": [{"field": "genre", "op": "in", "value": ["rock", "jazz"]}],
            "grants": [
                {"value": "xp", "per_unit": {"field": "minutes", "factor": 2, "max": 100}},
                {"value": "coins", "amount": 5},
            ],
        },
    )
    user = gm.people["ursula"]
    await gm.emit(user, {"minutes": 30, "genre": "rock"})
    await gm.emit(user, {"minutes": 30, "genre": "pop"})  # predicate does not match
    await gm.emit(user, {"minutes": 90, "genre": "jazz"})
    async with gm.database.session() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT value, delta, kind, source_kind, rule_key, rule_version, "
                    "trigger_event_id IS NOT NULL "
                    "FROM gamification.transactions ORDER BY seq"
                )
            )
        ).all()
        events = (
            await session.execute(
                text("SELECT type, payload FROM events.events WHERE type = 'reward.granted'")
            )
        ).all()
    assert [tuple(r) for r in rows] == [
        ("xp", 60, "grant", "reward_rule", "listen", 1, True),
        ("coins", 5, "grant", "reward_rule", "listen", 1, True),
        ("xp", 100, "grant", "reward_rule", "listen", 1, True),
        ("coins", 5, "grant", "reward_rule", "listen", 1, True),
    ]
    assert len(events) == 4 and events[0].payload == {
        "value": "xp",
        "amount": 60,
        "source": "reward_rule",
        "rule": "listen",
        "version": 1,
    }
    # redelivery: the dispatcher replays nothing new, and a direct duplicate is a no-op
    envelope = gm.envelope(user)
    first = await gm.module.pipeline.process(envelope)
    again = await gm.module.pipeline.process(envelope)
    assert first.granted == 2 and again.granted == 0
    assert await gm.balance(user, "xp") == 220 and await gm.balance(user, "coins") == 15
    assert {r.category for r in outbox.sent} >= {"gamification.reward", "gamification.level_up"}
    assert all(r.audience.ids == (user,) for r in outbox.sent)  # type: ignore[union-attr]


async def test_concurrent_events_for_one_user(gm: GamHarness) -> None:
    await gm.rule("listen", {"event_type": "media.played", "grants": [{"value": "coins", "amount": 3}]})
    user = gm.people["ursula"]
    envelopes = [gm.envelope(user, at=gm.clock.now() + timedelta(seconds=i + 1)) for i in range(10)]
    await asyncio.gather(*(gm.module.pipeline.process(e) for e in envelopes + envelopes[:3]))
    assert await gm.balance(user, "coins") == 30
    assert (await verify(gm.database)).ok


async def test_events_without_rules_or_user_are_ignored(gm: GamHarness) -> None:
    await gm.emit(gm.people["ursula"])  # no rule yet
    await gm.rule("listen", {"event_type": "media.played", "grants": [{"value": "xp", "amount": 1}]})
    anonymous = replace(gm.envelope(gm.people["ursula"]), actor_user_id=None)
    assert (await gm.module.pipeline.process(anonymous)).granted == 0
    async with gm.database.session() as session:
        assert await session.scalar(text("SELECT count(*) FROM gamification.transactions")) == 0
