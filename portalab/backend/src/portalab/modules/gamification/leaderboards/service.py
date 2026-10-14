"""Leaderboards (T037; FR-031, R13, CD-016): rankings materialized into ``leaderboard_snapshots`` by a job
and filtered **at read time** by each member's 021 ``progression`` visibility on the leaderboard surface.

* metrics ``xp``, ``level``, ``contribution``, ``achievements`` (``coins`` only when enabled); periods
  ``all`` (balances) and ``month``/``week`` (earned in the window: grants, manual grants and corrections);
  ``level`` is all-time only;
* only active accounts are ranked (tombstoned and suspended accounts never appear);
* issue 120: ties broken by the member's other values (XP, Contribution, Coins), then shared (ex aequo);
* #66: a member this viewer may not see keeps their place as an anonymous entry — no name, no avatar, no
  profile, an id tied to the place and never to them; the viewer always gets their own position;
* #66: each entry tells the places gained or lost against the board of 24 hours before;
* issue 120: every active member is on the board, even with nothing earned yet — after the others, with
  the score of a beginner."""

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.economy import (
    PERIODS,
    LeaderboardEntry,
    LeaderboardPeriod,
    LeaderboardView,
)
from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.identity_directory import MEMBERS
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import NotFound
from portalab.core.time import Clock, utc_now
from portalab.core.visibility_port import Redacted, VisibilityFilter
from portalab.modules.gamification.leaderboards.periods import period_start
from portalab.modules.gamification.levels.service import LevelService
from portalab.modules.gamification.models import (
    Balance,
    LeaderboardSnapshot,
    LedgerTransaction,
    UserAchievement,
)
from portalab.modules.gamification.observability import metrics

DATUM = "progression"
EARNED = ("grant", "manual", "correction")
# issue 120: what breaks a tie on each board, in order — then the places are shared
TIES: dict[str, tuple[str, ...]] = {
    "xp": ("contribution", "coins"),
    "level": ("xp", "contribution", "coins"),
    "contribution": ("xp", "coins"),
    "coins": ("xp", "contribution"),
    "achievements": ("xp", "contribution", "coins"),
}
MAX_ENTRIES = 5000
MOVES_SINCE = timedelta(hours=24)  # #66: places gained or lost since a day


def anonymous_id(metric: str, period: str, rank: int) -> UUID:
    """#66: what stands for a member who keeps their progression private — tied to the place, never to
    the member (no name, no avatar, no profile behind it)."""
    return uuid5(NAMESPACE_URL, f"portalab:leaderboard:{metric}:{period}:{rank}")


class LeaderboardService:
    def __init__(
        self,
        database: Database,
        levels: LevelService,
        visibility: VisibilityFilter,
        capabilities: CapabilityRegistry,
        config: Any,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.levels = levels
        self.visibility = visibility
        self.capabilities = capabilities
        self.config = config
        self.clock = clock

    def metrics(self) -> Sequence[str]:
        config = self.config()
        offered = [
            m for m in config.leaderboard_metrics if m in ("xp", "level", "contribution", "achievements")
        ]
        return [*offered, "coins"] if config.leaderboard_include_coins else offered

    def _check(self, metric: str, period: str) -> None:
        if metric not in self.metrics() or period not in PERIODS or (metric == "level" and period != "all"):
            raise NotFound("No such leaderboard.", code="economy.leaderboard_not_found")

    # --- computation -------------------------------------------------------------------------------
    async def _active(self, users: list[UUID]) -> set[UUID]:
        providers = self.capabilities.system_providers(DIRECTORY)
        if not providers:
            return set(users)
        directory = providers[0].provider
        return {u for u in users if await directory.is_active_account(u)}

    async def _members(self) -> list[UUID]:
        """Issue 120: every active member, by name — those who earned nothing yet are ranked too."""
        providers = self.capabilities.system_providers(MEMBERS)
        if not providers:
            return []
        listing = providers[0].provider
        members: list[UUID] = []
        offset: int | None = 0
        while offset is not None and len(members) < MAX_ENTRIES:
            page = await listing.active_members(offset=offset, limit=200)
            members.extend(entry.id for entry in page.items)
            offset = page.next_offset
        return members

    async def _values(
        self, value: str, start: datetime | None, until: datetime | None = None
    ) -> dict[UUID, int]:
        """Each member's ``value`` (``xp``, ``contribution``, ``coins`` or ``achievements``): the balance
        (all time, now), else what the ledger says up to ``until`` — earned in the window for a period."""
        async with self.database.session() as session:
            if value == "achievements":
                statement = select(UserAchievement.user_id, func.count()).group_by(UserAchievement.user_id)
                if start is not None:
                    statement = statement.where(UserAchievement.unlocked_at >= start)
                if until is not None:
                    statement = statement.where(UserAchievement.unlocked_at < until)
            elif start is None and until is None:
                statement = select(Balance.user_id, Balance.amount).where(Balance.value == value)
            else:
                statement = (
                    select(LedgerTransaction.user_id, func.sum(LedgerTransaction.delta))
                    .where(LedgerTransaction.value == value)
                    .group_by(LedgerTransaction.user_id)
                )
                if until is not None:
                    statement = statement.where(LedgerTransaction.occurred_at < until)
                if start is not None:
                    statement = statement.where(
                        LedgerTransaction.kind.in_(EARNED), LedgerTransaction.occurred_at >= start
                    )
            rows = (await session.execute(statement)).all()
        return {user: max(0, int(amount or 0)) for user, amount in rows}

    async def _ranking(
        self, metric: str, start: datetime | None, members: list[UUID], until: datetime | None = None
    ) -> list[list[Any]]:
        """``[user, score, rank]``, best first. Issue 120: a tie on the board's value is broken by the
        member's other values (XP, Contribution, Coins); when all are equal, the places are shared (ex
        aequo: 1, 2, 2, 4). Every active member is ranked, those with nothing earned after the others."""
        primary = "xp" if metric == "level" else metric
        scores = await self._values(primary, start, until)
        if metric == "level":
            async with self.database.session() as session:
                curve = await self.levels.curve(session)
            scores = {user: curve.level_for(xp) for user, xp in scores.items()}
            beginner = curve.level_for(0)
        else:
            beginner = 0
        ties = [await self._values(value, start, until) for value in TIES[metric]]
        named = {user: index for index, user in enumerate(members)}  # by name among full ties
        scored = [user for user, score in scores.items() if score > beginner or user in named]
        active = await self._active([user for user in scored if user not in named])
        users = [user for user in scored if user in named or user in active]
        users += [user for user in members if user not in scores]

        def values(user: UUID) -> tuple[int, ...]:
            return (scores.get(user, beginner), *(tie.get(user, 0) for tie in ties))

        ordered = sorted(
            users, key=lambda u: (tuple(-v for v in values(u)), named.get(u, len(named)), str(u))
        )[:MAX_ENTRIES]
        ranking: list[list[Any]] = []
        for position, user in enumerate(ordered, 1):
            same = ranking and values(UUID(ranking[-1][0])) == values(user)
            ranking.append([str(user), values(user)[0], ranking[-1][2] if same else position])
        return ranking

    async def compute(self, metric: str, period: LeaderboardPeriod) -> LeaderboardSnapshot:
        self._check(metric, period)
        now = utc_now(self.clock)
        start = period_start(period, now, self.config().timezone)
        members = await self._members()
        entries = await self._ranking(metric, start, members)
        until = now - MOVES_SINCE
        previous: list[list[Any]] = []
        if start is None or until > start:  # #66: the board as it stood a day before
            previous = await self._ranking(metric, start, members, until)
            floor = previous[-1][1] if previous else 0
            if all(score == floor for _user, score, _rank in previous):
                previous = []  # nothing earned yet then: no move to tell, nobody « new »
        statement = insert(LeaderboardSnapshot).values(
            metric=metric,
            period=period,
            period_start=start,
            computed_at=now,
            entries=entries,
            previous=previous,
        )
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                statement.on_conflict_do_update(
                    index_elements=[LeaderboardSnapshot.metric, LeaderboardSnapshot.period],
                    set_={
                        "period_start": start,
                        "computed_at": now,
                        "entries": entries,
                        "previous": previous,
                    },
                )
            )
        metrics.increment("gamification.leaderboards.computed")
        return LeaderboardSnapshot(
            metric=metric,
            period=period,
            period_start=start,
            computed_at=now,
            entries=entries,
            previous=previous,
        )

    async def refresh(self, *, force: bool = False) -> int:
        """Recompute every offered board whose snapshot is older than ``refreshMinutes`` (or force)."""
        due = utc_now(self.clock) - timedelta(minutes=max(1, self.config().leaderboard_refresh_minutes))
        async with self.database.session() as session:
            existing = {
                (s.metric, s.period): s.computed_at
                for s in (await session.execute(select(LeaderboardSnapshot))).scalars()
            }
        done = 0
        for metric in self.metrics():
            for period in PERIODS if metric != "level" else ("all",):
                at = existing.get((metric, period))
                if force or at is None or at <= due:
                    await self.compute(metric, period)
                    done += 1
        return done

    # --- reads -------------------------------------------------------------------------------------
    async def _snapshot(self, metric: str, period: LeaderboardPeriod) -> LeaderboardSnapshot:
        self._check(metric, period)
        async with self.database.session() as session:
            snapshot = await session.get(LeaderboardSnapshot, (metric, period))
        current = period_start(period, utc_now(self.clock), self.config().timezone)
        if snapshot is None or snapshot.period_start != current:
            snapshot = await self.compute(metric, period)
        return snapshot

    async def _shown(self, viewer: Principal, user: UUID) -> bool:
        try:
            result = await self.visibility.filter(viewer, user, DATUM, None, True, surface="leaderboard")  # type: ignore[call-arg]
        except TypeError:
            result = await self.visibility.filter(viewer, user, DATUM, None, True)
        return not isinstance(result, Redacted)

    async def board(
        self, viewer: Principal, metric: str, period: LeaderboardPeriod = "all", *, limit: int = 50
    ) -> LeaderboardView:
        limit = max(1, min(limit, 100))
        snapshot = await self._snapshot(metric, period)
        me = viewer.acting_for or viewer.user_id
        shown: dict[UUID, bool] = {}

        async def visible(user: UUID) -> bool:
            if user not in shown:
                shown[user] = user == me or await self._shown(viewer, user)
            return shown[user]

        # #66: the ranks of a day before
        before = {
            UUID(e[0]): int(e[2]) if len(e) > 2 else i for i, e in enumerate(snapshot.previous or [], 1)
        }
        had = {UUID(e[0]): int(e[1]) for e in snapshot.previous or []}
        # issue 120: the tail tied on the lowest score, unchanged since the day before, does not « move »
        floor = int(snapshot.entries[-1][1]) if snapshot.entries else 0
        entries: list[LeaderboardEntry] = []
        mine: LeaderboardEntry | None = None
        for position, stored in enumerate(snapshot.entries, 1):
            user, score = UUID(stored[0]), stored[1]
            rank = int(stored[2]) if len(stored) > 2 else position  # issue 120: ex aequo share a place
            hidden = not await visible(user)  # #66: kept in the ranking, as an anonymous member
            was = before.get(user)
            # issue 120: a member who had nothing the day before and now has is new on the board too
            new = bool(before) and (was is None or (had.get(user) == 0 and int(score) > 0))
            entry = LeaderboardEntry(
                rank,
                anonymous_id(metric, period, position) if hidden else user,
                int(score),
                user == me,
                change=(
                    (was - rank)
                    if was is not None and not new and not (int(score) == floor == had.get(user))
                    else None
                ),
                new=new,
                anonymous=hidden,
            )
            if len(entries) < limit:
                entries.append(entry)
            if user == me:
                mine = entry
            if mine is not None and len(entries) >= limit:
                break
            if me is None and len(entries) >= limit:
                break
        return LeaderboardView(metric, period, snapshot.computed_at, tuple(entries), mine)

    async def forget(self, user: UUID) -> None:
        """Erasure: drop the user from every snapshot at once (the next job run agrees)."""
        async with self.database.unit_of_work() as uow:
            for snapshot in (
                await uow.session.execute(select(LeaderboardSnapshot).with_for_update())
            ).scalars():
                kept = [e for e in snapshot.entries if e[0] != str(user)]
                if len(kept) != len(snapshot.entries):
                    snapshot.entries = kept
                earlier = [e for e in snapshot.previous or [] if e[0] != str(user)]
                if len(earlier) != len(snapshot.previous or []):
                    snapshot.previous = earlier
