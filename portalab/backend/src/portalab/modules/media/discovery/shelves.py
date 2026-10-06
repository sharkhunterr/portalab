"""Discovery (T028; R13, OQ-118): shelves ``new|recent|continue|trending|recommended`` behind a
``RecommendationProvider`` port. The baseline recommender is deterministic: genre/people affinity from the
viewer's own history plus community popularity (distinct finishers over 30 days, only counted above the
cohort floor). Every shelf is permission- and privacy-bounded and an empty shelf names a next action."""

from collections import Counter
from collections.abc import Sequence
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from portalab.capabilities.media_core import RECOMMENDATIONS
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.media.discovery.recent import Recent, recent_releases, recently_added
from portalab.modules.media.history.projection import HistoryProjection
from portalab.modules.media.models import HistoryEntry, MediaObject, ObjectTag
from portalab.modules.media.observability import log

SHELVES = ("new", "released", "recent", "continue", "trending", "recommended")
COHORT = 5
NEXT_ACTION = {
    "new": "browse",
    "released": "browse",
    "recent": "browse",
    "continue": "browse",
    "trending": "browse",
    "recommended": "link_account",
}


class BaselineRecommender:
    def __init__(self, database: Database, *, clock: Clock | None = None) -> None:
        self.database = database
        self.clock = clock

    async def recommend(self, viewer: Principal, *, limit: int) -> Sequence[UUID]:
        user = viewer.acting_for or viewer.user_id
        if user is None:
            return []
        async with self.database.session() as session:
            seen = {
                row[0]
                for row in await session.execute(
                    select(HistoryEntry.object_id).where(HistoryEntry.user_id == user).distinct()
                )
            }
            if not seen:
                return []
            tags = Counter(
                (kind, value.casefold())
                for kind, value in await session.execute(
                    select(ObjectTag.tag_kind, ObjectTag.value).where(ObjectTag.object_id.in_(seen))
                )
            )
            if not tags:
                return []
            candidates = await session.execute(
                select(ObjectTag.object_id, ObjectTag.tag_kind, ObjectTag.value)
                .join(MediaObject, MediaObject.id == ObjectTag.object_id)
                .where(
                    MediaObject.status == "active",
                    MediaObject.available.is_(True),
                    MediaObject.parent_id.is_(None),
                    ObjectTag.object_id.not_in(seen),
                )
            )
            scores: Counter[UUID] = Counter()
            for object_id, kind, value in candidates:
                scores[object_id] += tags.get((kind, value.casefold()), 0) * (2 if kind == "person" else 1)
        return [
            object_id
            for object_id, score in sorted(scores.items(), key=lambda p: (-p[1], str(p[0])))
            if score
        ][:limit]


class Discovery:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        history: HistoryProjection,
        config: Any,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.history = history
        self.config = config
        self.clock = clock

    async def recent(
        self, name: str, *, limit: int, kinds: Sequence[str] | None = None
    ) -> list[tuple[MediaObject, Recent]]:
        """027: « new » (added last) or « released » (came out last) works with their date and episode."""
        async with self.database.session() as session:
            recents = (
                await recent_releases(session, utc_now(self.clock).date(), limit=limit, kinds=kinds)
                if name == "released"
                else await recently_added(session, limit=limit, kinds=kinds)
            )
            rows = {row.id: row for row in await self._ordered(session, [r.object_id for r in recents])}
        return [(rows[r.object_id], r) for r in recents if r.object_id in rows]

    async def shelf(self, name: str, viewer: Principal) -> tuple[list[MediaObject], str | None]:
        user = viewer.acting_for or viewer.user_id
        size = max(1, min(self.config().discovery_shelf_size, 50))
        now = utc_now(self.clock)
        if name in ("new", "released"):  # 027: the services' own dates, newest first
            found = [row for row, _ in await self.recent(name, limit=size)]
            return found, (None if found else NEXT_ACTION[name])
        rows: Sequence[MediaObject]
        async with self.database.session() as session:
            if name == "recent" and user is not None:
                ids = [
                    r[0]
                    for r in await session.execute(
                        select(HistoryEntry.object_id, func.max(HistoryEntry.occurred_at).label("at"))
                        .where(HistoryEntry.user_id == user)
                        .group_by(HistoryEntry.object_id)
                        .order_by(func.max(HistoryEntry.occurred_at).desc())
                        .limit(size)
                    )
                ]
                rows = await self._ordered(session, ids)
            elif name == "continue" and user is not None:
                rows = [o for _, o in await self.history.continue_items(user, limit=size)]
            elif name == "trending":
                since = now - timedelta(days=30)
                ids = [
                    r[0]
                    for r in await session.execute(
                        select(HistoryEntry.object_id)
                        .where(HistoryEntry.occurred_at >= since, HistoryEntry.completed.is_(True))
                        .group_by(HistoryEntry.object_id)
                        .having(func.count(func.distinct(HistoryEntry.user_id)) >= COHORT)
                        .order_by(func.count(func.distinct(HistoryEntry.user_id)).desc())
                        .limit(size)
                    )
                ]
                rows = await self._ordered(session, ids)
            elif name == "recommended":
                ids = await self._recommended(viewer, size)
                rows = await self._ordered(session, ids)
            else:
                rows = []
        items = list(rows)
        return items, (None if items else NEXT_ACTION.get(name, "browse"))

    async def _recommended(self, viewer: Principal, size: int) -> list[UUID]:
        try:
            providers = self.capabilities.system_providers(RECOMMENDATIONS)
        except Exception:
            providers = []
        for registration in providers:
            try:
                ids = list(await registration.provider.recommend(viewer, limit=size))
            except Exception:
                log.info("a recommendation provider failed")
                continue
            if ids:
                return ids
        return []

    @staticmethod
    async def _ordered(session: Any, ids: Sequence[UUID]) -> list[MediaObject]:
        if not ids:
            return []
        rows = {
            r.id: r
            for r in (
                await session.execute(
                    select(MediaObject).where(MediaObject.id.in_(list(ids)), MediaObject.status == "active")
                )
            ).scalars()
        }
        return [rows[i] for i in ids if i in rows]
