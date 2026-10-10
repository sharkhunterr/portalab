"""Leaderboards view (T018; US3, slice B): Community presents 013's leaderboards — metrics, periods, ranking,
opt-out and visibility all come from the ``economy.leaderboards`` provider (ranks honour each member's
leaderboard visibility at read time; the viewer always gets their own position). Community adds display
names only. When 013 is absent or failing the view is ``unavailable`` and the page still renders."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from portalab.capabilities.economy import LEADERBOARDS, LeaderboardEntry, LeaderboardPeriod
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.errors import NotFound
from portalab.modules.community.observability import log, metrics

State = Literal["available", "no-data", "unavailable"]


@dataclass(frozen=True, slots=True)
class RankedMember:
    rank: int
    user_id: UUID
    display_name: str | None
    score: int
    me: bool
    change: int | None = None  # #66: places gained (> 0) or lost (< 0) since a day
    new: bool = False
    anonymous: bool = False  # #66: a private member — no name, no avatar, no profile


@dataclass(frozen=True, slots=True)
class BoardView:
    metric: str
    period: str
    state: State
    computed_at: datetime | None = None
    entries: list[RankedMember] = field(default_factory=list)
    me: RankedMember | None = None


class LeaderboardsView:
    def __init__(self, capabilities: CapabilityRegistry, names: Any) -> None:
        self.capabilities = capabilities
        self.names = names  # async (UUID) -> str | None

    def _reader(self) -> Any | None:
        providers = self.capabilities.system_providers(LEADERBOARDS)
        return providers[0].provider if providers else None

    def metrics(self) -> list[str]:
        reader = self._reader()
        try:
            return list(reader.metrics()) if reader is not None else []
        except Exception:
            return []

    async def _ranked(self, entry: LeaderboardEntry) -> RankedMember:
        anonymous = bool(getattr(entry, "anonymous", False))
        return RankedMember(
            entry.rank,
            entry.user_id,
            None if anonymous else await self.names(entry.user_id),
            entry.score,
            entry.me,
            getattr(entry, "change", None),
            getattr(entry, "new", False),
            anonymous,
        )

    async def board(
        self, viewer: Principal, metric: str, period: LeaderboardPeriod = "all", *, limit: int = 50
    ) -> BoardView:
        reader = self._reader()
        if reader is None:
            return BoardView(metric, period, "unavailable")
        try:
            view = await reader.board(viewer, metric, period, limit=limit)
        except NotFound:
            raise
        except Exception as error:  # 013 down: this view degrades alone
            metrics.increment("community.leaderboards.unavailable")
            log.warning("leaderboard unavailable", extra={"error": type(error).__name__})
            return BoardView(metric, period, "unavailable")
        entries = [await self._ranked(e) for e in view.entries]
        return BoardView(
            metric,
            period,
            "available" if entries else "no-data",
            view.computed_at,
            entries,
            await self._ranked(view.me) if view.me else None,
        )
