"""013 T012 — rule versions: the version in force is chosen by the event's ``occurred_at``; a new version
never edits an old one; retirement ends a rule; closed schemas reject unknown attributes and fields; the
simulation writes nothing."""

import time
from datetime import UTC, datetime, timedelta

import pytest

from portalab.capabilities.events import EventType, EventTypeRegistry
from portalab.core.errors import ValidationFailed
from portalab.modules.gamification.rules.definition import RuleDefinition, parse_rule
from portalab.modules.gamification.rules.store import RuleStore, RuleVersion

T0 = datetime(2026, 10, 1, tzinfo=UTC)
TYPES = EventTypeRegistry()
TYPES.register(EventType("media.played", "test:media", rewardable=frozenset({"minutes"})))


def version(
    key: str, number: int, start: datetime, retired: datetime | None = None, amount: int = 10
) -> RuleVersion:
    definition = RuleDefinition.model_validate(
        {"event_type": "media.played", "grants": [{"value": "xp", "amount": amount}]}
    )
    return RuleVersion(key, number, definition, start, retired)


async def test_version_in_force_by_instant() -> None:
    store = RuleStore.__new__(RuleStore)
    store._published = (  # loaded versions, as the cache holds them
        time.monotonic(),
        [
            version("listen", 1, T0, amount=10),
            version("listen", 2, T0 + timedelta(days=2), amount=20),
            version("bonus", 1, T0, retired=T0 + timedelta(days=1)),
        ],
    )
    before = await store.in_force("media.played", T0 - timedelta(seconds=1))
    day1 = await store.in_force("media.played", T0 + timedelta(hours=1))
    day3 = await store.in_force("media.played", T0 + timedelta(days=3))
    assert before == []
    assert [(v.key, v.version) for v in day1] == [("bonus", 1), ("listen", 1)]
    assert [(v.key, v.version, v.definition.grants[0].amount) for v in day3] == [("listen", 2, 20)]
    assert await store.in_force("other.type", T0 + timedelta(days=3)) == []


@pytest.mark.parametrize(
    ("raw", "fragment"),
    [
        (
            {"event_type": "media.played", "grants": [{"value": "xp", "amount": 1}], "script": "x"},
            "not valid",
        ),
        ({"event_type": "media.played", "grants": [{"value": "gems", "amount": 1}]}, "not valid"),
        (
            {
                "event_type": "media.played",
                "grants": [{"value": "xp", "amount": 1}],
                "predicate": [{"field": "genre", "value": "x"}],
            },
            "rewardable",
        ),
        (
            {
                "event_type": "media.played",
                "grants": [{"value": "xp", "per_unit": {"field": "secret", "factor": 1}}],
            },
            "rewardable",
        ),
        ({"event_type": "unknown.type", "grants": [{"value": "xp", "amount": 1}]}, "Unknown event type"),
        ({"event_type": "reward.granted", "grants": [{"value": "xp", "amount": 1}]}, "economy events"),
        (
            {
                "event_type": "media.played",
                "grants": [{"value": "xp", "amount": 1}, {"value": "xp", "amount": 2}],
            },
            "One grant",
        ),
        ({"event_type": "media.played", "grants": [{"value": "xp"}]}, "not valid"),
    ],
)
def test_closed_schema(raw: dict[str, object], fragment: str) -> None:
    with pytest.raises(ValidationFailed) as error:
        parse_rule(raw, TYPES)
    assert fragment in str(error.value.detail) and error.value.code == "economy.rule_invalid"


@pytest.mark.integration
async def test_publish_is_append_only_and_simulation_writes_nothing(gm) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import text

    from portalab.modules.gamification.rules.simulate import simulate
    from tests.integration.gamification.conftest import SYSTEM

    await gm.rule("listen", {"event_type": "media.played", "grants": [{"value": "xp", "amount": 10}]})
    gm.clock.advance(timedelta(hours=1))
    await gm.rule("listen", {"event_type": "media.played", "grants": [{"value": "xp", "amount": 25}]})
    versions = await gm.module.rules.versions("listen")
    assert [(v.version, v.definition["grants"][0]["amount"]) for v in versions] == [(1, 10), (2, 25)]
    user = gm.people["ursula"]
    await gm.emit(user, at=gm.clock.now() - timedelta(minutes=30))  # late event: version 1 was in force
    await gm.emit(user, at=gm.clock.now() + timedelta(minutes=1))
    async with gm.database.session() as session:
        rows = (
            await session.execute(
                text("SELECT rule_version, delta FROM gamification.transactions ORDER BY seq")
            )
        ).all()
    assert [tuple(r) for r in rows] == [(1, 10), (2, 25)]
    results = await simulate(
        {
            "event_type": "media.played",
            "grants": [{"value": "coins", "per_unit": {"field": "minutes", "factor": 0.5, "max": 10}}],
        },
        [{"payload": {"minutes": 12, "genre": "x"}}, {"payload": {"minutes": 100, "genre": "x"}}],
        types=gm.ev.types,
        combiner=gm.module.combiner,
        cap=5.0,
        user=user,
        now=gm.clock.now(),
    )
    assert [r["grants"][0]["amount"] for r in results] == [6, 10]
    async with gm.database.session() as session:
        assert await session.scalar(text("SELECT count(*) FROM gamification.transactions")) == 2
    await gm.module.rules.retire(SYSTEM, "listen")
    gm.clock.advance(timedelta(minutes=5))
    await gm.emit(user)
    async with gm.database.session() as session:
        assert await session.scalar(text("SELECT count(*) FROM gamification.transactions")) == 2


def test_fixed_plus_per_unit() -> None:
    """027: a play gives its fixed part plus a part per minute watched (capped)."""
    from portalab.modules.gamification.calculator.calculator import base_amounts
    from portalab.modules.gamification.rules.definition import parse_rule

    rule = parse_rule(
        {
            "event_type": "media.playback_finished",
            "grants": [
                {
                    "value": "xp",
                    "amount": 10,
                    "per_unit": {"field": "duration_s", "factor": 1 / 60, "max": 180},
                }
            ],
        }
    )
    assert base_amounts(rule, {"duration_s": 1500}) == [("xp", 35)]  # 10 + 25 min
    assert base_amounts(rule, {"duration_s": 3 * 3600 * 2}) == [("xp", 190)]  # capped part
    assert base_amounts(rule, {}) == [("xp", 10)]


def test_a_rule_gives_a_contents_boosters() -> None:
    """Issue 234: boosters alone are a rule's reward — only for an action about a content."""
    from portalab.capabilities.events import EventType, EventTypeRegistry
    from portalab.core.errors import ValidationFailed
    from portalab.modules.gamification.rules.definition import parse_rule
    from portalab.modules.media.events import register_event_types

    types = EventTypeRegistry()
    register_event_types(types)
    rule = parse_rule({"event_type": "media.season_finished", "boosters": 1}, types)
    assert rule.boosters == 1 and rule.grants == []
    with pytest.raises(ValidationFailed):
        parse_rule({"event_type": "media.season_finished"}, types)  # gives nothing
    with pytest.raises(ValidationFailed):
        parse_rule({"event_type": "media.season_finished", "boosters": 4}, types)
    types.register(EventType(name="ticket.created", owner="t"))
    with pytest.raises(ValidationFailed):
        parse_rule({"event_type": "ticket.created", "boosters": 1}, types)  # about no content


def test_a_rule_gives_the_boosters_of_the_works_its_event_names() -> None:
    """Issue 356: the bingo's full card is about no content, but names the works its booster draws among."""
    from portalab.modules.games.events import register_event_types

    types = EventTypeRegistry()
    register_event_types(types)
    rule = parse_rule({"event_type": "games.bingo_card", "boosters": 1}, types)
    assert rule.boosters == 1
    with pytest.raises(ValidationFailed):
        parse_rule({"event_type": "games.bingo_line", "boosters": 1}, types)  # a line names none
