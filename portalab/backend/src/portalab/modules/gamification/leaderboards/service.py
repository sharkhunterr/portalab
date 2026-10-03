"""Leaderboards (T037; FR-031, R13, CD-016): rankings materialized into ``leaderboard_snapshots`` by a job
and filtered **at read time** by each member's 021 ``progression`` visibility on the leaderboard surface.

* metrics ``xp``, ``level``, ``contribution``, ``achievements`` (``coins`` only when enabled); periods
  ``all`` (balances) and ``month``/``week`` (earned in the window: grants, manual grants and corrections);
  ``level`` is all-time only;
* only active accounts are ranked (tombstoned and suspended accounts never appear);
* ties: earliest attainment first (the ledger sequence or unlock time that reached the score), then id;
* ranks count only the members this viewer may see, so no gap reveals a hidden member; the viewer always
  gets their own position, even when they chose not to appear to others."""

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.economy import (
    PERIODS,
    LeaderboardEntry,
    LeaderboardPeriod,
    LeaderboardView,
)
from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
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
MAX_ENTRIES = 5000


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

    async def _rows(self, metric: str, start: datetime | None) -> list[tuple[UUID, int, Any]]:
        """``(user, score, attainment)`` with a positive score."""
        async with self.database.session() as session:
            if metric == "achievements":
                statement = select(
                    UserAchievement.user_id, func.count(), func.max(UserAchievement.unlocked_at)
                ).group_by(UserAchievement.user_id)
                if start is not None:
                    statement = statement.where(UserAchievement.unlocked_at >= start)
                return [(u, int(n), at) for u, n, at in (await session.execute(statement)).all()]
            value = "xp" if metric == "level" else metric
            if start is None:
                rows = (
                    await session.execute(
                        select(Balance.user_id, Balance.amount, Balance.last_seq).where(
                            Balance.value == value, Balance.amount > 0
                        )
                    )
                ).all()
                scored = [(u, int(a), int(seq)) for u, a, seq in rows]
                if metric == "level":
                    curve = await self.levels.curve(session)
                    scored = [(u, curve.level_for(a), seq) for u, a, seq in scored]
                return scored
            rows = (
                await session.execute(
                    select(
                        LedgerTransaction.user_id,
                        func.sum(LedgerTransaction.delta),
                        func.max(LedgerTransaction.seq),
                    )
                    .where(
                        LedgerTransaction.value == value,
                        LedgerTransaction.kind.in_(EARNED),
                        LedgerTransaction.occurred_at >= start,
                    )
                    .group_by(LedgerTransaction.user_id)
                )
            ).all()
            return [(u, int(total), int(seq)) for u, total, seq in rows if int(total or 0) > 0]

    async def compute(self, metric: str, period: LeaderboardPeriod) -> LeaderboardSnapshot:
        self._check(metric, period)
        now = utc_now(self.clock)
        start = period_start(period, now, self.config().timezone)
        rows = await self._rows(metric, start)
        active = await self._active([u for u, _, _ in rows])
        ranked = sorted(
            (r for r in rows if r[0] in active and r[1] > 0), key=lambda r: (-r[1], r[2], str(r[0]))
        )[:MAX_ENTRIES]
        entries = [[str(u), score] for u, score, _ in ranked]
        statement = insert(LeaderboardSnapshot).values(
            metric=metric, period=period, period_start=start, computed_at=now, entries=entries
        )
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                statement.on_conflict_do_update(
                    index_elements=[LeaderboardSnapshot.metric, LeaderboardSnapshot.period],
                    set_={"period_start": start, "computed_at": now, "entries": entries},
                )
            )
        metrics.increment("gamification.leaderboards.computed")
        return LeaderboardSnapshot(
            metric=metric, period=period, period_start=start, computed_at=now, entries=entries
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
        entries: list[LeaderboardEntry] = []
        mine: LeaderboardEntry | None = None
        rank = 0
        for raw_user, score in snapshot.entries:
            user = UUID(raw_user)
            if user != me and not await self._shown(viewer, user):
                continue
            rank += 1
            entry = LeaderboardEntry(rank, user, int(score), user == me)
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
