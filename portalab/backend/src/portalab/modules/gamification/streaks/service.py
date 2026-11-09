"""Play streaks (027): consecutive days on which a member did one of the counted things (by default:
finished a film or an episode). The longer the streak, the more the rewards of those very events are
multiplied — e.g. x1.5 from 2 days, x2 from 5 days. Provided as a reward modifier (``economy.modifiers``,
instance ``streak``), so it combines with campaigns under the global boost cap; the day of each counted
event is recorded at reward time (a missed day breaks the streak). Days follow the economy time zone."""

from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.economy import Modifier, Value
from portalab.capabilities.events import Envelope
from portalab.core.db import Database
from portalab.modules.gamification.models import StreakDay

MAX_DAYS = 366
RECENT = 14  # the days a streak's page draws, today last


class Tier(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    days: int = Field(ge=2, le=MAX_DAYS)
    multiplier: float = Field(gt=1, le=10)


class StreakConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = False
    event_types: list[str] = Field(default_factory=list, max_length=20)
    values: list[str] = Field(default_factory=lambda: ["xp"], max_length=3)
    tiers: list[Tier] = Field(default_factory=list, max_length=10)
    # #94: a sitting counts for the streak from this many seconds watched, listened to or read (when the
    # event tells them: ``watched_s``) — a play opened and closed at once does not keep a streak alive
    min_watched_s: int = Field(default=300, ge=0, le=86_400)


def parse_streak(raw: Any) -> StreakConfig:
    try:
        return StreakConfig.model_validate(raw or {})
    except ValidationError:
        return StreakConfig()


def multiplier_for(config: StreakConfig, days: int) -> float:
    """The multiplier of the highest tier reached (1 below the first tier)."""
    reached = [t.multiplier for t in config.tiers if days >= t.days]
    return max(reached) if reached else 1.0


class PaceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    factor: float = Field(default=1.0, ge=0.1, le=10)
    values: list[str] = Field(default_factory=lambda: ["xp"], max_length=3)


def parse_pace(raw: Any) -> PaceConfig:
    try:
        return PaceConfig.model_validate(raw or {})
    except ValidationError:
        return PaceConfig()


class Pace:
    """The overall pace (027): one factor on the gains of every rule, chosen by moving the progression
    curve (« members reach level N after a year ») rather than by editing each action. Provided as a
    reward modifier (instance ``pace``) so campaigns and streaks still combine with it under the cap."""

    def __init__(self, config: Callable[[], Any]) -> None:
        self.config = config

    async def modifiers_for(
        self, user: UUID, event: Envelope, value: Value, at: datetime
    ) -> Sequence[Modifier]:
        pace = parse_pace(self.config().pace)
        if value not in pace.values or abs(pace.factor - 1.0) < 1e-9:
            return []
        return [Modifier("pace", pace.factor)]


class Streaks:
    def __init__(self, database: Database, config: Callable[[], Any]) -> None:
        self.database = database
        self.config = config

    def settings(self) -> StreakConfig:
        return parse_streak(self.config().streak)

    def _day(self, at: datetime) -> date:
        try:
            zone = ZoneInfo(self.config().timezone or "UTC")
        except (ZoneInfoNotFoundError, ValueError):
            zone = ZoneInfo("UTC")
        return at.astimezone(zone).date()

    async def length(self, user: UUID, day: date) -> int:
        """Consecutive counted days ending on ``day`` (0 when ``day`` itself is not counted)."""
        async with self.database.session() as session:
            days = set(
                (
                    await session.execute(
                        select(StreakDay.day).where(
                            StreakDay.user_id == user, StreakDay.day > day - timedelta(days=MAX_DAYS)
                        )
                    )
                ).scalars()
            )
        length = 0
        while day - timedelta(days=length) in days:
            length += 1
        return length

    async def _days(self, at: datetime, users: Sequence[UUID] | None = None) -> dict[UUID, dict[date, bool]]:
        """The counted days of the last year (each: whether a freeze covered it), member by member."""
        query = select(StreakDay.user_id, StreakDay.day, StreakDay.frozen).where(
            StreakDay.day > self._day(at) - timedelta(days=MAX_DAYS)
        )
        if users is not None:
            query = query.where(StreakDay.user_id.in_(users))
        out: dict[UUID, dict[date, bool]] = {}
        async with self.database.session() as session:
            for user, day, frozen in (await session.execute(query)).all():
                out.setdefault(user, {})[day] = bool(frozen)
        return out

    def summary(self, days: dict[date, bool], today: date) -> dict[str, Any]:
        """#388: a member's streak as their page (and the administrators') draws it: today's streak (or
        yesterday's, still alive) and its multiplier, the next tier and all of them, whether today already
        counts, the longest streak of the year, its last day and the last days one by one (done, covered by
        a freeze, missed — today, still to come)."""
        config = self.settings()

        def run(end: date) -> int:
            length = 0
            while end - timedelta(days=length) in days:
                length += 1
            return length

        counted = today in days
        current = run(today) or run(today - timedelta(days=1))
        best, length, previous = 0, 0, None
        for day in sorted(days):
            length = length + 1 if previous is not None and day - previous == timedelta(days=1) else 1
            best, previous = max(best, length), day
        upcoming = [t for t in config.tiers if t.days > current]
        nxt = min(upcoming, key=lambda t: t.days) if upcoming else None
        recent = []
        for back in range(RECENT - 1, -1, -1):
            day = today - timedelta(days=back)
            state = "frozen" if days.get(day) else "done" if day in days else "missed"
            recent.append({"day": day, "state": "pending" if day == today and not counted else state})
        return {
            "enabled": config.enabled,
            "days": current,
            "multiplier": multiplier_for(config, current),
            "next": {"days": nxt.days, "multiplier": nxt.multiplier} if nxt else None,
            "tiers": [
                {"days": t.days, "multiplier": t.multiplier}
                for t in sorted(config.tiers, key=lambda t: t.days)
            ],
            "today": counted,
            "best": best,
            "last_day": max(days) if days else None,
            "recent": recent,
        }

    async def current(self, user: UUID, at: datetime) -> dict[str, Any]:
        """For the member's page: today's streak (or yesterday's, still alive), its multiplier, its days."""
        return self.summary((await self._days(at, [user])).get(user, {}), self._day(at))

    async def board(self, at: datetime) -> list[tuple[UUID, dict[str, Any]]]:
        """#389: for the administrators, every member who kept a streak this year, the longest streaks
        now first."""
        today = self._day(at)
        rows = [(user, self.summary(days, today)) for user, days in (await self._days(at)).items()]
        return sorted(
            rows, key=lambda r: (-r[1]["days"], -r[1]["best"], -(r[1]["last_day"] or date.min).toordinal())
        )

    async def bonus(self, user: UUID, value: Value, at: datetime) -> list[Modifier]:
        """Issue 226: the streak's multiplier for a reward (a quest, an achievement…) — read, never counted:
        today's streak, or yesterday's still alive."""
        config = self.settings()
        if not config.enabled or value not in config.values:
            return []
        today = self._day(at)
        days = await self.length(user, today) or await self.length(user, today - timedelta(days=1))
        factor = multiplier_for(config, days)
        return [Modifier(f"streak:{days}d", factor)] if factor > 1 else []

    async def modifiers_for(
        self, user: UUID, event: Envelope, value: Value, at: datetime
    ) -> Sequence[Modifier]:
        config = self.settings()
        if not config.enabled or event.type not in config.event_types:
            return []
        watched = event.payload.get("watched_s")
        if isinstance(watched, int | float) and watched < config.min_watched_s:
            return []  # too short to count
        day = self._day(at)
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                insert(StreakDay).values(user_id=user, day=day).on_conflict_do_nothing()
            )
        if value not in config.values:
            return []
        days = await self.length(user, day)
        factor = multiplier_for(config, days)
        return [Modifier(f"streak:{days}d", factor)] if factor > 1 else []
