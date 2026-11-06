"""My requests (027, after Telemetra's « Demandes » tab): the funnel of my requests over a period, films vs
series, requests over time against the previous period, how many of them I actually watched, my rank among
requesters (anonymous: a position, never names), the community's most watched requested titles, the genres
I request against the genres I watch — and what is coming soon: my requests being downloaded or imported
(the download managers' queues) and those with a release date (their calendars).

issue 222: the audience of what was asked — how many other members watched my requests (a number, never who),
which of my requests drew the most of them, and the requesters' podiums: who asks the most, whose requests
the most members watch, whose requests are watched by the most per title. A requester is named there as on
the leaderboards (their ``progression`` visibility), else an anonymous member."""

import asyncio
import time
from collections import Counter
from collections.abc import Sequence
from contextlib import suppress
from datetime import UTC, date, datetime, timedelta
from statistics import median
from typing import Any, NamedTuple
from uuid import UUID

from sqlalchemy import String, and_, func, select

from portalab.capabilities.identity_directory import CAPABILITY as DIRECTORY
from portalab.capabilities.media import DOWNLOAD_CLIENTS, DOWNLOADS, SourceDownload, TorrentState, unwrap
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.core.visibility_port import Redacted, VisibilityFilter
from portalab.modules.media.common import strong_ids
from portalab.modules.media.insights.stats import Window, window
from portalab.modules.media.models import (
    Activity,
    MediaObject,
    MediaRequest,
    ObjectMetadata,
    ObjectTag,
)
from portalab.modules.media.requests.service import catalog_title, known_title

GROUPS = {
    "pending": ("pending",),
    "approved": ("approved", "processing"),
    "available": ("available",),
    "declined": ("declined", "failed", "cancelled"),
}
OPEN = ("pending", "approved", "processing")
QUEUE_TTL = 30
PODIUM = 5
PERTINENT_FROM = 3  # requests a requester needs to enter the « watched per title » podium
NAMED = "progression"  # issue 222: named on the requesters' podiums as on the leaderboards


def group_of(state: str) -> str:
    return next((group for group, states in GROUPS.items() if state in states), "pending")


SCREEN = ("movie", "series", "tv", "")


def kind_of(row: MediaRequest) -> str:
    """A film or a series — #378: else the title's own kind (a book, an audiobook, a game…)."""
    kind = str((row.external_ref or {}).get("kind") or "")
    if kind in ("series", "tv"):
        return "series"
    return "movie" if kind in SCREEN else kind[:40]


def lookup_of(row: MediaRequest) -> tuple[str, dict[str, str], str, None] | None:
    """What the metadata provider (TMDB) needs to find a film's or a series' poster — #378: nothing for
    another kind of title, whose cover the request keeps itself."""
    ref = row.external_ref or {}
    if kind_of(row) not in ("movie", "series"):
        return None
    return kind_of(row), dict(ref.get("ids") or {}), str(ref.get("title") or ""), None


def told(row: MediaRequest) -> dict[str, Any]:
    """#378: a book's or a game's cover and sheet, as the request keeps them (a film's come from TMDB)."""
    ref = row.external_ref or {}
    return {key: ref[key] for key in ("cover", "sheet", "creators") if ref.get(key)}


def ids_of(row: MediaRequest) -> set[tuple[str, str]]:
    return set(strong_ids((row.external_ref or {}).get("ids") or {}).items())


class Reach(NamedTuple):
    """Issue 222: one request of the period and its audience among the other members."""

    key: str  # the requester: a member's id, else ``ext:`` and the external requester
    request: UUID
    object: UUID | None
    available: bool
    viewers: int  # other members (or media-server accounts) who watched it since it was asked
    plays: int


def _viewer() -> Any:
    """Who played: a member, else a media server's own account."""
    return func.coalesce(
        func.cast(Activity.user_id, String),
        func.concat(func.cast(Activity.service_id, String), ":", Activity.external_user_id),
    )


def _watched_by_others() -> Any:
    """A counted play of a request's title by someone else than its requester, after it was asked."""
    return and_(
        Activity.work_id == MediaRequest.object_id,
        Activity.counted.is_(True),
        Activity.started_at >= MediaRequest.requested_at,
        Activity.user_id.is_distinct_from(MediaRequest.requester_user_id),
    )


def title_of(row: MediaRequest) -> str:
    return str((row.external_ref or {}).get("title") or "?")


def arrived_at(row: MediaRequest) -> datetime | None:
    raw = (row.external_ref or {}).get("available_at")
    with suppress(ValueError, TypeError):
        return datetime.fromisoformat(str(raw)) if raw else None
    return None


BUCKETS = ("hour", "day", "week", "month", "more")


def bucket_of(hours: float) -> str:
    if hours <= 1:
        return "hour"
    if hours <= 24:
        return "day"
    if hours <= 168:
        return "week"
    return "month" if hours <= 720 else "more"


def _depth(
    win: Window,
    own: Sequence[Reach],
    everyone: Sequence[Reach],
    titles: dict[UUID, MediaRequest],
    plays: Sequence[tuple[UUID, datetime, str]],
    tags: dict[UUID, list[str]],
) -> dict[str, Any]:
    """Issue 222 (sold): the audience in depth — how fast another member watched what arrived, the genres
    of the requests the members watch (mine and the whole server's), films against series, my requests
    against everyone's, the long tail (plays a month after the arrival), and the plays over time."""
    first: dict[UUID, datetime] = {}
    late = 0
    for request, at, _ in plays:
        first[request] = min(at, first.get(request, at))
        row = titles.get(request)
        since = (arrived_at(row) or row.requested_at) if row is not None else None
        late += 1 if since is not None and at - since > timedelta(days=30) else 0
    delays: list[tuple[float, str]] = []
    waiting = 0
    for reach in own:
        row = titles.get(reach.request)
        if row is None or not reach.available:
            continue
        arrived = arrived_at(row)
        if reach.request not in first:
            waiting += 1
        elif arrived is not None:
            hours = max(0.0, (first[reach.request] - arrived).total_seconds() / 3600)
            delays.append((round(hours, 2), title_of(row)))
    delays.sort()
    buckets = Counter(bucket_of(h) for h, _ in delays)

    def genres(reaches: Sequence[Reach]) -> list[dict[str, Any]]:
        viewers: Counter[str] = Counter()
        requests: Counter[str] = Counter()
        for reach in reaches:
            for genre in tags.get(reach.object, []) if reach.object else []:
                viewers[genre] += reach.viewers
                requests[genre] += 1
        return [{"name": g, "viewers": v, "requests": requests[g]} for g, v in viewers.most_common(8) if v]

    def rates(reaches: Sequence[Reach]) -> dict[str, Any]:
        arrived = [r for r in reaches if r.available]
        if not arrived:
            return {"available": 0, "seen_rate": None, "viewers_per_request": None}
        seen = sum(1 for r in arrived if r.viewers)
        return {
            "available": len(arrived),
            "seen_rate": round(seen / len(arrived), 3),
            "viewers_per_request": round(sum(r.viewers for r in arrived) / len(arrived), 2),
        }

    kinds: dict[str, dict[str, Any]] = {}
    for kind in ("movie", "series"):
        chosen = [r for r in own if (row := titles.get(r.request)) is not None and kind_of(row) == kind]
        kinds[kind] = {"requests": len(chosen), "plays": sum(r.plays for r in chosen), **rates(chosen)}
    weekly = win.start is not None and (win.end - win.start).days <= 62
    over: Counter[str] = Counter()
    for _, at, _ in plays:
        day = at.astimezone(UTC).date()
        key = day - timedelta(days=day.weekday()) if weekly else day.replace(day=1)
        over[key.isoformat()] += 1
    return {
        "reactivity": {
            "median_hours": round(median(h for h, _ in delays), 2) if delays else None,
            "buckets": [{"key": k, "count": buckets.get(k, 0)} for k in BUCKETS],
            "waiting": waiting,
            "fastest": [{"title": t, "hours": h} for h, t in delays[:3]],
            "slowest": [{"title": t, "hours": h} for h, t in reversed(delays[-3:])],
        },
        "genres": {"mine": genres(own), "server": genres(everyone)},
        "kinds": kinds,
        "versus": {"mine": rates(own), "server": rates(everyone)},
        "late_share": round(late / len(plays), 3) if plays else None,
        "over_time": {
            "unit": "week" if weekly else "month",
            "points": [{"date": k, "plays": v} for k, v in sorted(over.items())],
        },
    }


class RequestInsights:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        upcoming: Any,
        *,
        clock: Clock | None = None,
        enricher: Any = None,
        visibility: VisibilityFilter | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.upcoming = upcoming
        self.enricher = enricher
        self.visibility = visibility
        self.clock = clock
        self._queue: tuple[float, list[SourceDownload]] | None = None

    # --- statistics --------------------------------------------------------------------------------
    async def overview(self, user: UUID, period: str, viewer: Principal | None = None) -> dict[str, Any]:
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
            audiences = await self._audiences(session, win)
        timeline = self._timeline(win, mine, previous)
        acquisition = await self._acquisition(mine)
        delta = (
            prev_rank["position"] - ranking["position"]
            if prev_rank and prev_rank["position"] and ranking["position"]
            else None
        )
        return {
            "period": {"key": win.key, "start": win.start.isoformat() if win.start else None},
            "summary": {"total": len(mine), **{g: int(summary.get(g, 0)) for g in GROUPS}},
            "previous_total": len(previous) if before else None,
            # #378: the books, audiobooks, games… asked for too
            "by_kind": {"movie": int(kinds.get("movie", 0)), "series": int(kinds.get("series", 0))}
            | {kind: int(count) for kind, count in kinds.items() if kind not in ("movie", "series")},
            "timeline": timeline,
            "watched": {
                "requested": len(mine),
                "watched": watched,
                "rate": round(watched / len(mine), 3) if mine else None,
            },
            "ranking": {**ranking, "delta": delta},
            "top_watched": top,
            "genres": genres,
            "acquisition": acquisition,
            **(await self._audience_sections(win, audiences, mine, user, viewer)),
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

    # --- issue 222: the audience of requests ---------------------------------------------------------------
    async def _audiences(self, session: Any, win: Window) -> list[Reach]:
        """Each request of the period: its requester's key (a member's id, else ``ext:`` and the external
        requester), how many *other* members watched its title after it was asked, and their plays."""
        who = func.coalesce(
            func.cast(MediaRequest.requester_user_id, String),
            func.concat("ext:", MediaRequest.external_ref["requester"].astext),
        )
        query = (
            select(
                who,
                MediaRequest.id,
                MediaRequest.object_id,
                MediaRequest.state == "available",
                func.count(func.distinct(_viewer())).filter(Activity.id.is_not(None)),
                func.count(Activity.id),
            )
            .outerjoin(Activity, _watched_by_others())
            .where(MediaRequest.requested_at < win.end, who.is_not(None))
            .group_by(who, MediaRequest.id)
        )
        if win.start is not None:
            query = query.where(MediaRequest.requested_at >= win.start)
        return [
            Reach(str(k), i, o, bool(a), int(v), int(p))
            for k, i, o, a, v, p in (await session.execute(query)).all()
            if k
        ]

    async def _audience_sections(
        self, win: Window, audiences: Sequence[Reach], mine: Sequence[MediaRequest], user: UUID, viewer: Any
    ) -> dict[str, Any]:
        me = str(user)
        own = [r for r in audiences if r.key == me]
        titles = {r.id: r for r in mine}
        async with self.database.session() as session:
            plays = await self._plays_of(session, [r.request for r in own if r.viewers])
            tags = await self._genres_of(session, {r.object for r in audiences if r.viewers and r.object})
        ranked = sorted((r for r in own if r.viewers), key=lambda r: (-r.viewers, -r.plays))[:8]
        per: dict[str, dict[str, int]] = {}
        for reach in audiences:
            entry = per.setdefault(reach.key, {"requests": 0, "viewers": 0, "plays": 0, "titles": 0})
            entry["requests"] += 1
            entry["viewers"] += reach.viewers
            entry["plays"] += reach.plays
            entry["titles"] += 1 if reach.viewers else 0
        mine_total = per.get(me, {}).get("viewers", 0)
        ahead = sum(1 for k, e in per.items() if k != me and e["viewers"] > mine_total)
        return {
            "audience": {
                "requested": len(own),
                "seen": sum(1 for r in own if r.viewers),
                # the viewers of all my requests together: a member who watched two of them counts once
                "viewers": len({who for _, _, who in plays}),
                "plays": sum(r.plays for r in own),
            },
            "audience_titles": {
                "items": [
                    {
                        "id": str(row.object_id) if row.object_id else None,
                        "title": title_of(row),
                        "kind": kind_of(row),
                        "viewers": r.viewers,
                        "plays": r.plays,
                        "_lookup": lookup_of(row),
                        **told(row),
                    }
                    for r in ranked
                    if (row := titles.get(r.request)) is not None
                ],
                "position": 1 + ahead if mine_total else None,
                "total": sum(1 for e in per.values() if e["viewers"]),
            },
            "audience_depth": _depth(win, own, audiences, titles, plays, tags),
            "leaders": await self._leaders(per, me, viewer),
        }

    async def _plays_of(self, session: Any, requests: Sequence[UUID]) -> list[tuple[UUID, datetime, str]]:
        """Every play of another member on these requests' titles since they were asked: (request, when,
        who — a key, never shown)."""
        if not requests:
            return []
        query = (
            select(MediaRequest.id, Activity.started_at, _viewer())
            .join(Activity, _watched_by_others())
            .where(MediaRequest.id.in_(requests))
        )
        return [(i, at, str(who)) for i, at, who in (await session.execute(query)).all()]

    async def _genres_of(self, session: Any, objects: set[UUID]) -> dict[UUID, list[str]]:
        if not objects:
            return {}
        out: dict[UUID, list[str]] = {}
        rows = await session.execute(
            select(ObjectTag.object_id, ObjectTag.value).where(
                ObjectTag.object_id.in_(objects), ObjectTag.tag_kind == "genre"
            )
        )
        for object_id, value in rows.all():
            out.setdefault(object_id, []).append(str(value))
        return out

    async def _leaders(
        self, per: dict[str, dict[str, int]], me: str, viewer: Principal | None
    ) -> dict[str, list[dict[str, Any]]]:
        """The requesters' podiums of the period: the most requests, the most viewers of their requests,
        the most viewers per request (from ``PERTINENT_FROM`` requests). Ex aequo share a place."""
        names: dict[str, str | None] = {}

        async def name(key: str) -> str | None:
            if key not in names:
                names[key] = await self._name(key, viewer)
            return names[key]

        async def podium(score: Any, keys: Sequence[str]) -> list[dict[str, Any]]:
            ordered = sorted(keys, key=lambda k: -score(per[k]))
            out: list[dict[str, Any]] = []
            for key in ordered[:PODIUM]:
                value = score(per[key])
                rank = 1 + sum(1 for k in keys if score(per[k]) > value)
                out.append(
                    {
                        "rank": rank,
                        "me": key == me,
                        "name": None if key == me else await name(key),
                        "value": round(value, 2) if isinstance(value, float) else value,
                        "requests": per[key]["requests"],
                    }
                )
            return out

        everyone = list(per)
        watched = [k for k in everyone if per[k]["viewers"]]
        pertinent = [k for k in watched if per[k]["requests"] >= PERTINENT_FROM]
        return {
            "requests": await podium(lambda e: e["requests"], everyone),
            "viewers": await podium(lambda e: e["viewers"], watched),
            "per_request": await podium(lambda e: e["viewers"] / e["requests"], pertinent),
        }

    async def _name(self, key: str, viewer: Principal | None) -> str | None:
        """A member's name when they show on the leaderboards; an external requester stays anonymous."""
        if viewer is None or self.visibility is None or key.startswith("ext:"):
            return None
        with suppress(Exception):
            user = UUID(key)
            try:
                shown = await self.visibility.filter(viewer, user, NAMED, None, True, surface="leaderboard")  # type: ignore[call-arg]
            except TypeError:
                shown = await self.visibility.filter(viewer, user, NAMED, None, True)
            if isinstance(shown, Redacted):
                return None
            providers = self.capabilities.system_providers(DIRECTORY)
            summary = await providers[0].provider.get_user_summary(user) if providers else None
            return summary.display_name if summary else None
        return None

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

    async def _release_dates(self, rows: Sequence[MediaRequest]) -> dict[UUID, date]:
        """Release date of each request: the enriched catalog (TMDB) first, else a cached lookup."""
        out: dict[UUID, date] = {}
        objects = {r.object_id for r in rows if r.object_id}
        if objects:
            async with self.database.session() as session:
                found = await session.execute(
                    select(ObjectMetadata.object_id, ObjectMetadata.data["release_date"].astext).where(
                        ObjectMetadata.object_id.in_(objects), ObjectMetadata.status == "found"
                    )
                )
                known = {object_id: value for object_id, value in found.all() if value}
        else:
            known = {}
        gate = asyncio.Semaphore(6)

        async def one(row: MediaRequest) -> None:
            raw = known.get(row.object_id) if row.object_id else None
            lookup = lookup_of(row)
            if raw is None and self.enricher is not None and lookup is not None:
                async with gate:
                    raw = (await self.enricher.brief(*lookup))["release_date"]
            if raw:
                with suppress(ValueError):
                    out[row.id] = date.fromisoformat(str(raw)[:10])

        await asyncio.gather(*(one(r) for r in rows[:150]))  # bounded: lookups are cached afterwards
        return out

    async def _acquisition(self, mine: Sequence[MediaRequest]) -> dict[str, Any]:
        """027: how long my requests took to become available, and when I asked compared with the release
        (before release, its first month, its first year, or an older title)."""
        released = await self._release_dates(mine)
        buckets = dict.fromkeys(BUCKETS, 0)
        moments: dict[str, list[float]] = {k: [] for k in ("before", "month", "year", "catalog", "unknown")}
        points: list[dict[str, Any]] = []
        delays: list[float] = []
        pending = 0
        for row in mine:
            arrived = (row.external_ref or {}).get("available_at")
            when = datetime.fromisoformat(arrived) if arrived else None
            release = released.get(row.id)
            asked_after = (row.requested_at.date() - release).days if release else None
            moment = (
                "unknown"
                if asked_after is None
                else "before"
                if asked_after < 0
                else "month"
                if asked_after <= 31
                else "year"
                if asked_after <= 365
                else "catalog"
            )
            if row.state != "available" or when is None:
                pending += 1 if row.state in OPEN else 0
                continue
            hours = max(0.0, (when - row.requested_at).total_seconds() / 3600)
            delays.append(hours)
            moments[moment].append(hours)
            buckets[bucket_of(hours)] += 1
            points.append(
                {
                    "title": str((row.external_ref or {}).get("title") or "?"),
                    "kind": kind_of(row),
                    "hours": round(hours, 2),
                    "asked_after_days": asked_after,
                    "moment": moment,
                    "id": str(row.object_id) if row.object_id else None,
                }
            )
        points.sort(key=lambda p: float(p["hours"]))
        return {
            "buckets": [{"key": k, "count": v} for k, v in buckets.items()],
            "pending": pending,
            "median_hours": round(median(delays), 2) if delays else None,
            "moments": [
                {"moment": k, "count": len(v), "median_hours": round(median(v), 2) if v else None}
                for k, v in moments.items()
                if v
            ],
            "points": points[:300],
            "fastest": points[:3],
            "slowest": list(reversed(points[-3:])),
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
            rows = list(
                (
                    await session.execute(
                        select(MediaRequest)
                        .where(MediaRequest.requester_user_id == user)
                        .order_by(MediaRequest.requested_at.desc())
                        .limit(limit)
                    )
                ).scalars()
            )
        await self.link_objects(rows)
        return rows

    async def link_objects(self, rows: Sequence[MediaRequest]) -> None:
        """027: requests made before their title reached the catalog are tied to it now (same strong id
        and same kind), so every request opens its title's page."""
        loose = [r for r in rows if r.object_id is None and ids_of(r)]
        if not loose:
            return
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            for row in loose:
                ref = row.external_ref or {}
                found = await catalog_title(
                    uow.session, ref.get("ids") or {}, str(ref.get("kind") or ""), ref.get("title"), now
                )
                if found is not None:
                    stored = await uow.session.get(MediaRequest, row.id)
                    if stored is not None:
                        stored.object_id = found
                    row.object_id = found

    async def stages(self, rows: Sequence[MediaRequest]) -> dict[UUID, dict[str, Any]]:
        """027: where each request stands, in the words of the title's journey — cheap signals only (no
        call per title): the request's state, the catalog, the managers' queues, the release calendars."""
        open_rows = [r for r in rows if r.state in OPEN]
        downloads = await self.queue() if open_rows else []
        releases = await self.upcoming.list(120) if open_rows and self.upcoming is not None else []
        objects = {r.object_id for r in rows if r.object_id}
        available: set[UUID] = set()
        future: dict[UUID, str] = {}
        if objects:
            async with self.database.session() as session:
                available = set(
                    (
                        await session.execute(
                            select(MediaObject.id).where(
                                MediaObject.id.in_(objects), MediaObject.available.is_(True)
                            )
                        )
                    ).scalars()
                )
                today = utc_now(self.clock).date().isoformat()
                for object_id, value in (
                    await session.execute(
                        select(ObjectMetadata.object_id, ObjectMetadata.data["release_date"].astext).where(
                            ObjectMetadata.object_id.in_(objects), ObjectMetadata.status == "found"
                        )
                    )
                ).all():
                    if value and str(value)[:10] > today:
                        future[object_id] = str(value)[:10]
        out: dict[UUID, dict[str, Any]] = {}
        for row in rows:
            if row.state == "pending":
                out[row.id] = {"stage": "pending"}
                continue
            if row.state in ("declined", "cancelled", "failed"):
                out[row.id] = {"stage": row.state}
                continue
            if row.state == "available" or (row.object_id in available):
                out[row.id] = {"stage": "available"}
                continue
            ids = ids_of(row)
            same = ("movie",) if kind_of(row) == "movie" else ("episode", "series", "season")
            fetching = [d for d in downloads if d.kind in same and ids & set(strong_ids(d.ids).items())]
            if fetching:
                blocked = any(d.attention in ("import_blocked", "failed", "warning") for d in fetching)
                importing = any(d.status == "importing" for d in fetching)
                out[row.id] = {
                    "stage": "import_blocked" if blocked else "importing" if importing else "downloading",
                    "progress": round(sum(d.progress for d in fetching) / len(fetching), 3),
                }
                continue
            coming = [r for r in releases if ids & set(strong_ids(r.get("ids") or {}).items())]
            if coming:
                out[row.id] = {
                    "stage": "awaiting_release",
                    "at": coming[0]["at"],
                    "release_type": coming[0]["type"],
                }
            elif row.object_id in future:
                out[row.id] = {"stage": "awaiting_release", "at": future[row.object_id]}
            else:
                out[row.id] = {"stage": "searching"}
        return out

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

    async def torrents(self, downloads: Sequence[SourceDownload]) -> dict[str, TorrentState]:
        """The torrent clients' view of these downloads (by info hash): state, speeds, peers, ratio."""
        hashes = sorted({d.download_id for d in downloads if d.download_id})
        if not hashes:
            return {}
        try:
            providers = [r.provider for r in self.capabilities.system_providers(DOWNLOAD_CLIENTS)]
        except Exception:
            providers = []
        results = await asyncio.gather(
            *(asyncio.wait_for(p.torrents(hashes), timeout=10) for p in providers), return_exceptions=True
        )
        out: dict[str, TorrentState] = {}
        for result in results:
            if isinstance(result, BaseException):
                continue
            with suppress(Exception):
                for torrent in unwrap(result):
                    out[torrent.download_id] = torrent
        return out

    async def downloads(self, user: UUID | None, limit: int = 12) -> dict[str, Any]:
        """#58: what the download managers fetch or import now — one card per title (a series' episodes
        together), with the torrent clients' speed, time left and peers. Titles only, never who asked;
        ``user``: only the titles that member asked for."""
        queue = await self.queue()
        if user is not None and queue:
            mine: set[tuple[str, str]] = set()
            async with self.database.session() as session:
                rows = (
                    await session.execute(
                        select(MediaRequest)
                        .where(MediaRequest.requester_user_id == user, MediaRequest.state.in_(OPEN))
                        .limit(300)
                    )
                ).scalars()
                for row in rows:
                    mine |= ids_of(row)
            queue = [d for d in queue if mine & set(strong_ids(d.ids).items())]
        torrents = await self.torrents(queue)
        now = utc_now(self.clock)
        groups: dict[tuple[str, ...], list[SourceDownload]] = {}
        for download in queue:
            kind = "movie" if download.kind == "movie" else "series"
            name = (download.parent_title if kind == "series" else None) or download.title
            strong = tuple(f"{k}:{v}" for k, v in sorted(strong_ids(download.ids).items()))
            groups.setdefault((kind, *(strong or (name.casefold(),))), []).append(download)
        cards: list[dict[str, Any]] = []
        async with self.database.session() as session:
            for (kind, *_), items in groups.items():
                cards.append(await self._download_card(session, kind, items, torrents, now))
        order = {"downloading": 0, "importing": 1, "stalled": 2, "queued": 3, "paused": 4, "warning": 5}
        cards.sort(key=lambda c: (order.get(c["state"], 6), -c["progress"]))
        return {
            "items": cards[:limit],
            "count": len(cards),
            "speed": sum(c["speed"] for c in cards),
            "mine": user is not None,
        }

    async def _download_card(
        self,
        session: Any,
        kind: str,
        items: list[SourceDownload],
        torrents: dict[str, TorrentState],
        now: datetime,
    ) -> dict[str, Any]:
        first = items[0]
        title = (first.parent_title if kind == "series" else None) or first.title
        # a season pack is one torrent behind several episodes: each torrent counts once
        seen: dict[str, TorrentState] = {}
        for item in items:
            torrent = torrents.get(item.download_id or "")
            if torrent is not None:
                seen[torrent.download_id] = torrent
        transfers = list(seen.values())
        progress = [t.progress for t in transfers] or [d.progress for d in items]
        # an estimate already behind us says nothing: no time left rather than « 0 »
        etas = [t.eta_s for t in transfers if t.eta_s] or [
            left for d in items if d.eta and (left := round((d.eta - now).total_seconds())) > 0
        ]
        states = {t.state for t in transfers}
        if any(d.attention in ("failed", "warning", "import_blocked") for d in items):
            state = "warning"
        elif all(d.status == "importing" for d in items):
            state = "importing"
        elif "downloading" in states or (not transfers and any(d.status == "downloading" for d in items)):
            state = "downloading"
        elif states & {"stalled", "metadata", "error"}:
            state = "stalled"
        elif "paused" in states or any(d.status == "paused" for d in items):
            state = "paused"
        else:
            state = "queued" if any(d.status == "queued" for d in items) else "downloading"
        sizes = [t.size for t in transfers if t.size] or [d.size for d in items if d.size]
        card: dict[str, Any] = {
            "id": None,
            "title": title,
            "kind": kind,
            "state": state,
            "progress": round(sum(progress) / len(progress), 3),
            "speed": sum(t.download_speed for t in transfers),
            "upload_speed": sum(t.upload_speed for t in transfers),
            "eta_s": max(etas) if etas else None,
            "seeds": sum(t.seeds or 0 for t in transfers) if transfers else None,
            "peers": sum(t.peers or 0 for t in transfers) if transfers else None,
            "size": sum(sizes) if sizes else None,
            "count": len(items),
            "client": next((d.client for d in items if d.client), None)
            or next((t.client for t in transfers if t.client), None),
            "_lookup": (kind, dict(first.ids), title, None),
        }
        if kind == "series" and len(items) == 1 and first.season is not None:
            card["episode"] = {"season": first.season, "episode": first.episode, "title": first.title}
        found = await known_title(session, first.ids, kind)
        card["id"] = str(found) if found else None
        return card

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
        await self.link_objects(rows)  # 027: each one opens its title's page
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
                **told(row),
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
