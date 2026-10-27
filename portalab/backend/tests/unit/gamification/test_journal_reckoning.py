"""Issue 261: every gain of the journal says its sum — a rule's, a quest's, an achievement's, a level's, the
wheel's, an administrator's — and a spend or a correction none."""

from types import SimpleNamespace
from typing import Any

from portalab.modules.gamification.api.tuning import _reckoning


def row(**fields: Any) -> Any:
    return SimpleNamespace(
        **(
            {
                "source_kind": "daily",
                "kind": "grant",
                "value": "xp",
                "delta": 37,
                "base_amount": 25,
                "multiplier": 1.5,
                "modifiers": {},
            }
            | fields
        )
    )


def test_a_quest_says_its_reward_and_its_streak() -> None:
    reckoned = _reckoning(row(), None, None)
    assert reckoned is not None
    assert (reckoned.fixed, reckoned.base, reckoned.multiplier, reckoned.capped) == (25, 25, 1.5, False)


def test_an_achievement_a_level_the_wheel_an_administrator_say_their_amount() -> None:
    for kind, source in (
        ("grant", "achievement"),
        ("grant", "level_reward"),
        ("grant", "wheel"),
        ("manual", "manual"),
    ):
        reckoned = _reckoning(
            row(kind=kind, source_kind=source, delta=50, base_amount=50, multiplier=1), None, None
        )
        assert reckoned is not None and (reckoned.fixed, reckoned.multiplier) == (50, 1.0), source
    older = _reckoning(row(source_kind="level_reward", delta=30, base_amount=0, multiplier=1), None, None)
    assert older is not None and (older.fixed, older.base) == (30, 30)  # its base not kept: its amount


def test_a_rule_says_its_rate_and_what_it_counted() -> None:
    definition = {"grants": [{"value": "xp", "per_unit": {"field": "minutes", "factor": 1 / 3, "max": 80}}]}
    rule = row(
        source_kind="reward_rule",
        delta=5,
        base_amount=5,
        multiplier=1,
        modifiers={"measured": {"minutes": 16}},
    )
    reckoned = _reckoning(rule, definition, None)
    assert reckoned is not None and (reckoned.field, reckoned.quantity, reckoned.fixed) == (
        "minutes",
        16.0,
        None,
    )


def test_a_spend_or_a_correction_is_no_sum() -> None:
    assert _reckoning(row(kind="spend", source_kind="marketplace", delta=-50), None, None) is None
    assert _reckoning(row(kind="correction", source_kind="manual", delta=-5), None, None) is None
