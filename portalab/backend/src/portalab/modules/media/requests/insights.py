"""My requests (027, after Telemetra's « Demandes » tab): the funnel of my requests over a period, films vs
series, requests over time against the previous period, how many of them I actually watched, my rank among
requesters (anonymous: a position, never names), the community's most watched requested titles, the genres
I request against the genres I watch — and what is coming soon: my requests being downloaded or imported
(the download managers' queues) and those with a release date (their calendars)."""

import asyncio
import time
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import String, and_, func, select

from portalab.capabilities.media import DOWNLOADS, SourceDownload, unwrap
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.media.common import strong_ids
from portalab.modules.media.insights.stats import Window, window
from portalab.modules.media.models import Activity, MediaObject, MediaRequest, ObjectTag

GROUPS = {
    "pending": ("pending",),
    "approved": ("approved", "processing"),
    "available": ("available",),
    "declined": ("declined", "failed", "cancelled"),
}
OPEN = ("pending", "approved", "processing")
QUEUE_TTL = 30


def group_of(state: str) -> str:
    return next((group for group, states in GROUPS.items() if state in states), "pending")


def kind_of(row: MediaRequest) -> str:
    return "series" if (row.external_ref or {}).get("kind") in ("series", "tv") else "movie"


def lookup_of(row: MediaRequest) -> tuple[str, dict[str, str], str, None]:
    """What the metadata provider needs to find a request's poster."""
    ref = row.external_ref or {}
    return kind_of(row), dict(ref.get("ids") or {}), str(ref.get("title") or ""), None


def ids_of(row: MediaRequest) -> set[tuple[str, str]]:
    return set(strong_ids((row.external_ref or {}).get("ids") or {}).items())


class RequestInsights:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        upcoming: Any,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.upcoming = upcoming
        self.clock = clock
        self._queue: tuple[float, list[SourceDownload]] | None = None

    # --- statistics --------------------------------------------------------------------------------
    async def overview(self, user: UUID, period: str) -> dict[str, Any]:
        win = window(period, utc_now(self.clock))
        async with self.database.session() as session:
            mine = await self._requests(session, win, user)
            before = win.previous()
            previous = await self._requests(session, before, user) if before else []
            summary = Counter(group_of(r.state) for r in mine)
            kinds = Counter(kind_of(r) for r in mine)
            watched = await self._watched(session, mine, user)
            ranking = await self._ranking(session, win, user)
            prev_rank = await self._ranking(session, before, user) if before else None
            top = await self._top_watched(session, win)
            genres = await self._genres(session, win, mine, user)
        timeline = self._timeline(win, mine, previous)
        delta = (
            prev_rank["position"] - ranking["position"]
            if prev_rank and prev_rank["position"] and ranking["position"]
            else None
        )
        return {
            "period": {"key": win.key, "start": win.start.isoformat() if win.start else None},
            "summary": {"total": len(mine), **{g: int(summary.get(g, 0)) for g in GROUPS}},
            "previous_total": len(previous) if before else None,
            "by_kind": {"movie": int(kinds.get("movie", 0)), "series": int(kinds.get("series", 0))},
            "timeline": timeline,
            "watched": {
                "requested": len(mine),
                "watched": watched,
                "rate": round(watched / len(mine), 3) if mine else None,
            },
            "ranking": {**ranking, "delta": delta},
            "top_watched": top,
            "genres": genres,
        }

    async def _requests(self, session: Any, win: Window, user: UUID | None) -> list[MediaRequest]:
        query = select(MediaRequest).where(MediaRequest.requested_at < win.end)
        if win.start is not None:
            query = query.where(MediaRequest.requested_at >= win.start)
        if user is not None:
            query = query.where(MediaRequest.requester_user_id == user)
        return list((await session.execute(query)).scalars())

    async def _watched(self, session: Any, mine: Sequence[MediaRequest], user: UUID) -> int:
        objects = {r.object_id for r in mine if r.object_id}
        if not objects:
            return 0
        rows = await session.execute(
            select(func.count(func.distinct(Activity.work_id))).where(
                Activity.user_id == user, Activity.counted.is_(True), Activity.work_id.in_(objects)
            )
        )
        return int(rows.scalar() or 0)

    async def _ranking(self, session: Any, win: Window, user: UUID) -> dict[str, Any]:
        who = func.coalesce(
            func.cast(MediaRequest.requester_user_id, String),
            func.concat("ext:", MediaRequest.external_ref["requester"].astext),
        )
        query = select(who, func.count()).where(MediaRequest.requested_at < win.end, who.is_not(None))
        if win.start is not None:
            query = query.where(MediaRequest.requested_at >= win.start)
        counts = {str(k): int(n) for k, n in (await session.execute(query.group_by(who))).all() if k}
        mine = counts.get(str(user), 0)
        position = 1 + sum(1 for k, n in counts.items() if k != str(user) and n > mine) if mine else None
        return {"position": position, "total": len(counts), "count": mine}

    async def _top_watched(self, session: Any, win: Window) -> list[dict[str, Any]]:
        requested = select(MediaRequest.object_id).where(
            MediaRequest.object_id.is_not(None), MediaRequest.requested_at < win.end
        )
        if win.start is not None:
            requested = requested.where(MediaRequest.requested_at >= win.start)
        plays = (
            select(
                Activity.work_id, func.count().label("plays"), func.sum(Activity.watched_s).label("seconds")
            )
            .where(Activity.counted.is_(True), Activity.work_id.in_(requested))
            .group_by(Activity.work_id)
            .order_by(func.count().desc())
            .limit(12)
        )
        sub = plays.subquery()
        rows = (
            await session.execute(
                select(MediaObject.id, MediaObject.title, MediaObject.kind, sub.c.plays, sub.c.seconds)
                .join(sub, MediaObject.id == sub.c.work_id)
                .order_by(sub.c.plays.desc())
            )
        ).all()
        return [
            {"id": str(i), "title": t, "kind": k, "plays": int(p), "seconds": float(s or 0)}
            for i, t, k, p, s in rows
        ]

    async def _genres(
        self, session: Any, win: Window, mine: Sequence[MediaRequest], user: UUID
    ) -> dict[str, list[dict[str, Any]]]:
        objects = {r.object_id for r in mine if r.object_id}
        requested: list[tuple[str, int]] = []
        if objects:
            requested = [
                (str(v), int(n))
                for v, n in (
                    await session.execute(
                        select(ObjectTag.value, func.count())
                        .where(ObjectTag.object_id.in_(objects), ObjectTag.tag_kind == "genre")
                        .group_by(ObjectTag.value)
                        .order_by(func.count().desc())
                        .limit(8)
                    )
                ).all()
            ]
        query = (
            select(ObjectTag.value, func.count(func.distinct(Activity.work_id)))
            .join(ObjectTag, and_(ObjectTag.object_id == Activity.work_id, ObjectTag.tag_kind == "genre"))
            .where(Activity.user_id == user, Activity.counted.is_(True), Activity.started_at < win.end)
        )
        if win.start is not None:
            query = query.where(Activity.started_at >= win.start)
        watched = [
            (str(v), int(n))
            for v, n in (
                await session.execute(query.group_by(ObjectTag.value).order_by(func.count().desc()).limit(8))
            ).all()
        ]
        return {
            "requested": [{"name": n, "value": v} for n, v in requested],
            "watched": [{"name": n, "value": v} for n, v in watched],
        }

    def _timeline(
        self, win: Window, mine: Sequence[MediaRequest], previous: Sequence[MediaRequest]
    ) -> dict[str, Any]:
        end = win.end
        start = win.start or min((r.requested_at for r in mine), default=end - timedelta(days=30))
        days = max(1, (end - start).days)
        unit = "day" if days <= 62 else ("week" if days <= 400 else "month")

        def bucket(at: datetime) -> str:
            at = at.astimezone(UTC)
            if unit == "day":
                return at.date().isoformat()
            if unit == "week":
                return (at.date() - timedelta(days=at.weekday())).isoformat()
            return at.date().replace(day=1).isoformat()

        shift = (end - start) if win.start is not None else timedelta(0)
        current = Counter(bucket(r.requested_at) for r in mine)
        before = Counter(bucket(r.requested_at + shift) for r in previous)
        keys: list[str] = []
        cursor = start
        while cursor < end:
            key = bucket(cursor)
            if key not in keys:
                keys.append(key)
            cursor += timedelta(days=1)
        return {
            "unit": unit,
            "points": [{"date": k, "count": current.get(k, 0), "previous": before.get(k, 0)} for k in keys],
        }

    # --- list ----------------------------------------------------------------------------------------
    async def mine(self, user: UUID, limit: int = 300) -> list[MediaRequest]:
        async with self.database.session() as session:
            return list(
                (
                    await session.execute(
                        select(MediaRequest)
                        .where(MediaRequest.requester_user_id == user)
                        .order_by(MediaRequest.requested_at.desc())
                        .limit(limit)
                    )
                ).scalars()
            )

    # --- coming soon ---------------------------------------------------------------------------------
    async def queue(self) -> list[SourceDownload]:
        if self._queue and time.monotonic() - self._queue[0] < QUEUE_TTL:
            return self._queue[1]
        try:
            providers = [r.provider for r in self.capabilities.system_providers(DOWNLOADS)]
        except Exception:
            providers = []
        results = await asyncio.gather(
            *(asyncio.wait_for(p.queue(), timeout=15) for p in providers), return_exceptions=True
        )
        items: list[SourceDownload] = []
        for result in results:
            if not isinstance(result, BaseException):
                try:
                    items.extend(unwrap(result))
                except Exception:  # noqa: S112 — an unavailable queue is skipped
                    continue
        self._queue = (time.monotonic(), items)
        return items

    async def soon(self, user: UUID | None, limit: int = 20) -> list[dict[str, Any]]:
        """Open requests (mine, or everyone's) being downloaded or imported, or with a release date."""
        async with self.database.session() as session:
            query = select(MediaRequest).where(MediaRequest.state.in_(OPEN))
            if user is not None:
                query = query.where(MediaRequest.requester_user_id == user)
            rows = list(
                (await session.execute(query.order_by(MediaRequest.requested_at.desc()).limit(300))).scalars()
            )
        if not rows:
            return []
        downloads = await self.queue()
        releases = await self.upcoming.list(60) if self.upcoming is not None else []
        out: list[dict[str, Any]] = []
        for row in rows:
            ids = ids_of(row)
            if not ids:
                continue
            fetching = [d for d in downloads if ids & set(strong_ids(d.ids).items())]
            coming = [r for r in releases if ids & set(strong_ids(r.get("ids") or {}).items())]
            if not fetching and not coming:
                continue
            item: dict[str, Any] = {
                "request_id": str(row.id),
                "id": str(row.object_id) if row.object_id else None,
                "title": str((row.external_ref or {}).get("title") or "?"),
                "kind": kind_of(row),
                "state": row.state,
                "requested_at": row.requested_at.isoformat(),
                "_lookup": lookup_of(row),
            }
            if fetching:
                importing = any(d.status == "importing" for d in fetching)
                item["phase"] = "importing" if importing else fetching[0].status
                item["progress"] = round(sum(d.progress for d in fetching) / len(fetching), 3)
                item["count"] = len(fetching)
                etas = [d.eta for d in fetching if d.eta]
                item["eta"] = max(etas).isoformat() if etas else None
                first = fetching[0]
                if first.season is not None:
                    item["episode"] = {"season": first.season, "episode": first.episode, "title": first.title}
            else:
                nxt = coming[0]
                item["phase"] = "release"
                item["release_at"] = nxt["at"]
                item["release_type"] = nxt["type"]
                if nxt.get("season") is not None:
                    item["episode"] = {
                        "season": nxt["season"],
                        "episode": nxt["episode"],
                        "title": nxt["title"],
                    }
            out.append(item)
        order = {
            "importing": 0,
            "downloading": 1,
            "queued": 2,
            "paused": 3,
            "warning": 4,
            "failed": 5,
            "release": 6,
        }
        out.sort(
            key=lambda i: (order.get(i["phase"], 9), -(i.get("progress") or 0), i.get("release_at") or "")
        )
        return out[:limit]
