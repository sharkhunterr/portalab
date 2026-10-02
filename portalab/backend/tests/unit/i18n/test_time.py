"""026 T022 — one instant in several zones; DST gap/overlap resolved by policy (never an error); a
wall-clock schedule fires once per day across transitions; unknown zone ⇒ default + flag."""

from datetime import UTC, datetime, time, timedelta

from portalab.capabilities.i18n import LocaleContext
from portalab.modules.i18n.time.renderer import (
    Schedule,
    TimeRenderer,
    next_occurrence,
    resolve_wall_clock,
    zone,
)

R = TimeRenderer()
INSTANT = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


def test_one_instant_many_zones() -> None:
    tokyo = R.render_instant(INSTANT, LocaleContext(locale="en", time_zone="Asia/Tokyo", hour_cycle="h23"))
    ny = R.render_instant(INSTANT, LocaleContext(locale="en", time_zone="America/New_York", hour_cycle="h23"))
    assert tokyo.endswith("21:00") and ny.endswith("08:00")


def local(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    """A wall-clock (local, zone-less) time, as a schedule intent stores it."""
    return datetime(year, month, day, hour, minute)  # noqa: DTZ001 — intentionally naive


def test_gap_and_overlap() -> None:
    gap = resolve_wall_clock(local(2026, 3, 29, 2, 30), "Europe/Paris")  # 02:30 does not exist
    assert gap == datetime(2026, 3, 29, 1, 30, tzinfo=UTC)  # moved forward to 03:30 CEST
    backward = resolve_wall_clock(local(2026, 3, 29, 2, 30), "Europe/Paris", "gap_backward|overlap_earlier")
    assert backward == datetime(2026, 3, 29, 0, 30, tzinfo=UTC)  # 01:30 CET
    early = resolve_wall_clock(local(2026, 10, 25, 2, 30), "Europe/Paris")  # 02:30 happens twice
    late = resolve_wall_clock(local(2026, 10, 25, 2, 30), "Europe/Paris", "gap_forward|overlap_later")
    assert early == datetime(2026, 10, 25, 0, 30, tzinfo=UTC) and late == datetime(
        2026, 10, 25, 1, 30, tzinfo=UTC
    )


def test_wall_clock_schedule_across_dst() -> None:
    schedule = Schedule(mode="wall_clock", at=time(2, 30), time_zone="Europe/Paris")
    after = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
    fired = []
    for _ in range(4):
        after = next_occurrence(schedule, after)
        fired.append(after)
    assert len(set(fired)) == 4 and fired == sorted(fired)
    assert {(f - fired[0]).days for f in fired} == {0, 1, 2, 3}  # once per day, none skipped or doubled
    absolute = Schedule(
        mode="absolute", every=timedelta(hours=24), anchor=datetime(2026, 10, 24, 0, 30, tzinfo=UTC)
    )
    assert next_occurrence(absolute, datetime(2026, 10, 25, 1, 0, tzinfo=UTC)) == datetime(
        2026, 10, 26, 0, 30, tzinfo=UTC
    )


def test_unknown_zone_flagged() -> None:
    tz, ok = zone("Mars/Olympus")
    assert str(tz) == "UTC" and ok is False
