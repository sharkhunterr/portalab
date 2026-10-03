"""013 T020 — anti-abuse: cooldown withholds repeats, period caps trim to what remains, diminishing returns
(geometric and steps), windows keyed by ``occurred_at`` in the economy time zone, applied equally to the
three values, multipliers never exceeding caps."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from portalab.modules.gamification.antiabuse.windows import window_start


def test_windows_follow_the_economy_time_zone() -> None:
    at = datetime(2026, 10, 7, 23, 30, tzinfo=UTC)  # Wednesday 23:30 UTC = Thursday 01:30 in Paris
    assert window_start("day", at, "UTC") == datetime(2026, 10, 7, tzinfo=UTC)
    assert window_start("day", at, "Europe/Paris") == datetime(2026, 10, 7, 22, tzinfo=UTC)
    assert window_start("week", at, "UTC") == datetime(2026, 10, 5, tzinfo=UTC)
    assert window_start("hour", at, "Nowhere/Invalid") == datetime(2026, 10, 7, 23, tzinfo=UTC)


async def amounts(gm) -> list[tuple[str, int]]:  # type: ignore[no-untyped-def]
    async with gm.database.session() as session:
        rows = await session.execute(text("SELECT value, delta FROM gamification.transactions ORDER BY seq"))
        return [tuple(r) for r in rows.all()]  # type: ignore[misc]


async def withheld(gm) -> list[tuple[str, str]]:  # type: ignore[no-untyped-def]
    async with gm.database.session() as session:
        rows = await session.execute(
            text("SELECT reason, status FROM gamification.withheld ORDER BY occurred_at")
        )
        return [tuple(r) for r in rows.all()]  # type: ignore[misc]


@pytest.mark.integration
async def test_cooldown_and_caps(gm) -> None:  # type: ignore[no-untyped-def]
    await gm.rule(
        "listen",
        {
            "event_type": "media.played",
            "multiplier": 3,
            "grants": [{"value": "xp", "amount": 10}, {"value": "coins", "amount": 10}],
            "limits": {"cooldown_seconds": 60, "caps": [{"period": "day", "max_amount": 45}]},
        },
    )
    user = gm.people["ursula"]
    gm.clock.advance(timedelta(days=2))  # the rule has been in force for two days
    start = gm.clock.now() + timedelta(seconds=1)
    for offset in (0, 30, 120, 240):  # the 30 s repeat is inside the cooldown
        await gm.module.pipeline.process(gm.envelope(user, at=start + timedelta(seconds=offset)))
    assert await amounts(gm) == [
        ("xp", 30),
        ("coins", 30),
        ("xp", 15),
        ("coins", 15),
    ]  # x3 then trimmed to 45
    assert await withheld(gm) == [("cooldown", "dropped")] * 2 + [("cap", "dropped")] * 2
    late = start - timedelta(days=1)  # a late event belongs to yesterday's window
    await gm.module.pipeline.process(gm.envelope(user, at=late))
    assert (await amounts(gm))[-2:] == [("xp", 30), ("coins", 30)]


@pytest.mark.integration
@pytest.mark.parametrize(
    ("diminishing", "expected"),
    [
        ({"kind": "geometric", "factor": 0.5}, [16, 8, 4, 2]),
        ({"kind": "steps", "steps": [1, 0.5, 0.25]}, [16, 8, 4, 4]),
    ],
)
async def test_diminishing_returns(gm, diminishing, expected) -> None:  # type: ignore[no-untyped-def]
    await gm.rule(
        "listen",
        {
            "event_type": "media.played",
            "grants": [{"value": "contribution", "amount": 16}],
            "limits": {"diminishing": diminishing},
        },
    )
    user = gm.people["ursula"]
    for offset in range(4):
        await gm.module.pipeline.process(gm.envelope(user, at=gm.clock.now() + timedelta(minutes=offset + 1)))
    assert [delta for _, delta in await amounts(gm)] == expected
