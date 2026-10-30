"""Media statistics (027, « like Telemetra, but better »): what was watched, listened to and read, for one
member (``me``) or the whole server (``all``), over a period and a category.

Totals and timelines come from the daily aggregates; rankings, the weekday-by-hour heat map, records and
platforms from the raw rows of the period (only ``counted`` rows: a play reported by two sources counts
once). Server-wide figures are anonymous for members: names of members, devices and the recent plays of
others are only given to media managers.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Select, and_, distinct, extract, func, literal, select

from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.media.insights.aggregate import NIL, completed_clause
from portalab.modules.media.models import (
    Activity,
    ActivityDaily,
    MediaObject,
    MediaRequest,
    ObjectMetadata,
    ObjectTag,
    SourceItem,
)

CATEGORIES: dict[str, tuple[str, ...]] = {
    # #283: games stay out of « all » — a game played is no time watched, listened to or read
    "all": ("movie", "episode", "live", "track", "book", "audiobook", "radio", "other"),
    "movies": ("movie",),
    "series": ("episode",),
    "live": ("live",),
    "music": ("track",),
    "books": ("book",),
    "audiobooks": ("audiobook",),
    "radio": ("radio",),
    "games": ("game",),
}
# #283: the tab each kind a service holds or tells opens (a series' seasons and episodes, an album's tracks…)
CATEGORY_OF_KIND = {
    "movie": "movies",
    "series": "series",
    "season": "series",
    "episode": "series",
    "live": "live",
    "artist": "music",
    "album": "music",
    "track": "music",
    "book": "books",
    "audiobook": "audiobooks",
    "radio": "radio",
    "game": "games",
}
PERIODS = {"7d": 7, "30d": 30, "90d": 90, "365d": 365}
TOP = 10


@dataclass(frozen=True, slots=True)
class Window:
    start: datetime | None
    end: datetime
    key: str

    @property
    def days(self) -> int | None:
        return (self.end - self.start).days if self.start else None

    def previous(self) -> "Window | None":
        if self.start is None:
            return None
        return Window(self.start - (self.end - self.start), self.start, self.key)


def window(period: str, now: datetime) -> Window:
    end = datetime(now.year, now.month, now.day, tzinfo=UTC) + timedelta(days=1)
    if period in PERIODS:
        return Window(end - timedelta(days=PERIODS[period]), end, period)
    if period == "ytd":  # 027: since the 1st of January
        return Window(datetime(now.year, 1, 1, tzinfo=UTC), end, period)
    if period.isdigit() and len(period) == 4:  # a calendar year: « my 2025 »
        year = int(period)
        return Window(datetime(year, 1, 1, tzinfo=UTC), datetime(year + 1, 1, 1, tzinfo=UTC), period)
    return Window(None, end, "all")


def work_key() -> Any:
    """What identifies a work in rankings: its catalog object, else its series or album, else its title."""
    return func.coalesce(
        func.cast(Activity.work_id, Activity.title.type), Activity.parent_title, Activity.title
    )


def _point(day: date) -> dict[str, Any]:
    return {"date": day.isoformat(), "seconds": {}, "plays": 0, "plays_by_kind": {}}


class InsightsQuery:
    def __init__(self, database: Database, *, clock: Clock | None = None) -> None:
        self.database = database
        self.clock = clock

    async def categories(self, services: Sequence[UUID], *, radio: bool = False) -> list[str]:
        """#283: the categories a configured service feeds — its catalog or its history holds that kind —, in
        the tabs' order, « all » first. ``services``: the services connected now (a removed one opens none);
        ``radio``: a station is connected (its tab shows before anyone listened)."""
        if not services:
            return ["all", "radio"] if radio else ["all"]
        async with self.database.session() as session:
            kinds = set(
                (
                    await session.scalars(
                        select(distinct(SourceItem.kind)).where(
                            SourceItem.service_id.in_(services), SourceItem.active.is_(True)
                        )
                    )
                ).all()
            )
            kinds |= set(
                (
                    await session.scalars(
                        select(distinct(Activity.kind)).where(Activity.service_id.in_(services))
                    )
                ).all()
            )
        fed = {CATEGORY_OF_KIND[k] for k in kinds if k in CATEGORY_OF_KIND} | ({"radio"} if radio else set())
        return ["all", *(c for c in CATEGORIES if c != "all" and c in fed)]

    def _rows(self, win: Window, kinds: Sequence[str], user: UUID | None, *columns: Any) -> Select[Any]:
        query = select(*columns).where(
            Activity.counted.is_(True), Activity.kind.in_(kinds), Activity.started_at < win.end
        )
        if win.start is not None:
            query = query.where(Activity.started_at >= win.start)
        if user is not None:
            query = query.where(Activity.user_id == user)
        return query

    def _daily(self, win: Window, kinds: Sequence[str], user: UUID | None, *columns: Any) -> Select[Any]:
        query = select(*columns).where(ActivityDaily.kind.in_(kinds), ActivityDaily.day < win.end)
        if win.start is not None:
            query = query.where(ActivityDaily.day >= win.start)
        if user is not None:
            query = query.where(ActivityDaily.user_key == user)
        return query

    async def overview(
        self,
        *,
        period: str,
        category: str,
        user: UUID | None,
        manager: bool,
        tz: str = "UTC",
        top: int = TOP,
    ) -> dict[str, Any]:
        now = utc_now(self.clock)
        win = window(period, now)
        kinds = CATEGORIES.get(category, CATEGORIES["all"])
        zone = ZoneInfo(tz)
        detailed = user is not None or manager  # devices, recent plays and names
        async with self.database.session() as session:
            totals = (
                await session.execute(
                    self._daily(
                        win,
                        kinds,
                        user,
                        func.coalesce(func.sum(ActivityDaily.plays), 0),
                        func.coalesce(func.sum(ActivityDaily.completed), 0),
                        func.coalesce(func.sum(ActivityDaily.seconds), 0.0),
                        func.count(distinct(ActivityDaily.day)),
                    )
                )
            ).one()
            works = await session.scalar(
                self._rows(
                    win,
                    kinds,
                    user,
                    func.count(distinct(work_key())),
                )
            )
            members = None
            if user is None:
                members = await session.scalar(
                    self._daily(win, kinds, None, func.count(distinct(ActivityDaily.user_key))).where(
                        ActivityDaily.user_key != literal(NIL).cast(ActivityDaily.user_key.type)
                    )
                )
            previous = None
            before = win.previous()
            if before is not None:
                prev = (
                    await session.execute(
                        self._daily(
                            before,
                            kinds,
                            user,
                            func.coalesce(func.sum(ActivityDaily.plays), 0),
                            func.coalesce(func.sum(ActivityDaily.seconds), 0.0),
                        )
                    )
                ).one()
                previous = {"plays": int(prev[0]), "seconds": float(prev[1])}
            by_kind = [
                {"kind": kind, "plays": int(plays), "seconds": float(seconds)}
                for kind, plays, seconds in (
                    await session.execute(
                        self._daily(
                            win,
                            kinds,
                            user,
                            ActivityDaily.kind,
                            func.sum(ActivityDaily.plays),
                            func.sum(ActivityDaily.seconds),
                        ).group_by(ActivityDaily.kind)
                    )
                ).all()
            ]
            timeline = await self._timeline(session, win, kinds, user)
            heatmap = await self._heatmap(session, win, kinds, user, zone)
            top_works = await self._top_works(session, win, kinds, user, show_members=user is None, limit=top)
            genres = await self._tags(session, win, kinds, user, "genre")
            people = await self._tags(session, win, kinds, user, "person")
            decades = await self._decades(session, win, kinds, user)
            records = await self._records(session, win, kinds, user, zone)
            box_office = await self._box_office(session, win, kinds, user)
            platforms = await self._platforms(session, win, kinds, user) if detailed else None
            recent = await self._recent(session, win, kinds, user) if detailed else None
            leaderboard = await self._members(session, win, kinds) if manager and user is None else None
            requests = await self._requests(session, win, user) if category == "all" else None
            unattributed = None
            if manager and user is None:
                unattributed = await session.scalar(
                    self._rows(win, kinds, None, func.count()).where(Activity.user_id.is_(None))
                )
        return {
            "period": {
                "key": win.key,
                "start": win.start.isoformat() if win.start else None,
                "end": win.end.isoformat(),
            },
            "scope": "me" if user is not None else "all",
            "category": category if category in CATEGORIES else "all",
            "totals": {
                "plays": int(totals[0]),
                "completed": int(totals[1]),
                "seconds": float(totals[2]),
                "active_days": int(totals[3]),
                "works": int(works or 0),
                "members": int(members) if members is not None else None,
            },
            "previous": previous,
            "by_kind": sorted(by_kind, key=lambda k: -k["seconds"]),
            "timeline": timeline,
            "heatmap": heatmap,
            "top_works": top_works,
            "genres": genres,
            "people": people,
            "decades": decades,
            "records": records,
            "box_office": box_office,
            "platforms": platforms,
            "recent": recent,
            "members": leaderboard,
            "requests": requests,
            "unattributed": int(unattributed) if unattributed is not None else None,
        }

    async def _timeline(
        self, session: Any, win: Window, kinds: Sequence[str], user: UUID | None
    ) -> dict[str, Any]:
        days = win.days
        if days is None:
            first = await session.scalar(self._daily(win, kinds, user, func.min(ActivityDaily.day)))
            days = (win.end - first).days if first else 0
        unit = "day" if days <= 92 else ("week" if days <= 731 else "month")
        bucket = func.date_trunc(unit, ActivityDaily.day)
        rows = (
            await session.execute(
                self._daily(
                    win,
                    kinds,
                    user,
                    bucket.label("bucket"),
                    ActivityDaily.kind,
                    func.sum(ActivityDaily.seconds),
                    func.sum(ActivityDaily.plays),
                )
                .group_by(bucket, ActivityDaily.kind)
                .order_by(bucket)
            )
        ).all()
        points: dict[str, dict[str, Any]] = {}
        for at, kind, seconds, plays in rows:
            point = points.setdefault(at.date().isoformat(), _point(at.date()))
            point["seconds"][kind] = float(seconds)
            point["plays"] += int(plays)
            point["plays_by_kind"][kind] = int(plays)  # 027: the activity chart counts plays too
        if win.start is not None and unit == "day":  # days without activity are part of the story
            day = win.start
            while day < win.end:
                points.setdefault(
                    day.date().isoformat(), {"date": day.date().isoformat(), "seconds": {}, "plays": 0}
                )
                day += timedelta(days=1)
        return {"unit": unit, "points": sorted(points.values(), key=lambda p: p["date"])}

    async def _heatmap(
        self, session: Any, win: Window, kinds: Sequence[str], user: UUID | None, zone: ZoneInfo
    ) -> list[dict[str, Any]]:
        local = func.timezone(zone.key, Activity.started_at)
        weekday, hour = extract("isodow", local), extract("hour", local)
        rows = (
            await session.execute(
                self._rows(
                    win, kinds, user, weekday, hour, func.count(), func.sum(Activity.watched_s)
                ).group_by(weekday, hour)
            )
        ).all()
        return [
            {"weekday": int(d), "hour": int(h), "plays": int(n), "seconds": float(s or 0)}
            for d, h, n, s in rows
        ]

    async def _top_works(
        self,
        session: Any,
        win: Window,
        kinds: Sequence[str],
        user: UUID | None,
        *,
        show_members: bool,
        limit: int = TOP,
    ) -> list[dict[str, Any]]:
        label = func.coalesce(MediaObject.title, func.max(Activity.parent_title), func.max(Activity.title))
        key = func.coalesce(
            func.cast(Activity.work_id, Activity.title.type), Activity.parent_title, Activity.title
        )
        rows = (
            await session.execute(
                self._rows(
                    win,
                    kinds,
                    user,
                    key.label("key"),
                    Activity.work_id,
                    label,
                    func.max(MediaObject.kind),
                    func.max(MediaObject.year),
                    func.count(),
                    func.sum(Activity.watched_s),
                    func.count(distinct(Activity.user_id)),
                    func.max(Activity.kind),
                    func.max(Activity.started_at),
                )
                .outerjoin(MediaObject, MediaObject.id == Activity.work_id)
                .group_by(key, Activity.work_id, MediaObject.title)
                .order_by(func.sum(Activity.watched_s).desc(), func.count().desc())
                .limit(limit)
            )
        ).all()
        return [
            {
                "id": str(work) if work else None,
                "title": title,
                "kind": object_kind or ("series" if activity_kind == "episode" else activity_kind),
                "year": year,
                "plays": int(plays),
                "seconds": float(seconds or 0),
                "members": int(members) if show_members else None,
                "last_at": last.isoformat() if last else None,
            }
            for _key, work, title, object_kind, year, plays, seconds, members, activity_kind, last in rows
        ]

    async def _tags(
        self, session: Any, win: Window, kinds: Sequence[str], user: UUID | None, tag_kind: str
    ) -> list[dict[str, Any]]:
        rows = (
            await session.execute(
                self._rows(
                    win,
                    kinds,
                    user,
                    ObjectTag.value,
                    func.count(),
                    func.sum(Activity.watched_s),
                    func.count(distinct(Activity.work_id)),
                )
                .join(
                    ObjectTag, and_(ObjectTag.object_id == Activity.work_id, ObjectTag.tag_kind == tag_kind)
                )
                .group_by(ObjectTag.value)
                .order_by(func.sum(Activity.watched_s).desc(), func.count().desc())
                .limit(TOP)
            )
        ).all()
        return [
            {"name": name, "plays": int(plays), "seconds": float(seconds or 0), "works": int(works)}
            for name, plays, seconds, works in rows
        ]

    async def _decades(
        self, session: Any, win: Window, kinds: Sequence[str], user: UUID | None
    ) -> list[dict[str, Any]]:
        year = func.coalesce(MediaObject.year, Activity.year)
        decade = (func.floor(year / 10) * 10).label("decade")
        rows = (
            await session.execute(
                self._rows(win, kinds, user, decade, func.count(), func.sum(Activity.watched_s))
                .outerjoin(MediaObject, MediaObject.id == Activity.work_id)
                .where(year.is_not(None))
                .group_by(decade)
                .order_by(decade)
            )
        ).all()
        return [{"decade": int(d), "plays": int(n), "seconds": float(s or 0)} for d, n, s in rows]

    async def _records(
        self, session: Any, win: Window, kinds: Sequence[str], user: UUID | None, zone: ZoneInfo
    ) -> dict[str, Any]:
        longest = (
            await session.execute(
                self._rows(
                    win,
                    kinds,
                    user,
                    Activity.title,
                    Activity.parent_title,
                    Activity.watched_s,
                    Activity.started_at,
                )
                .order_by(Activity.watched_s.desc())
                .limit(1)
            )
        ).first()
        local_day = func.date(func.timezone(zone.key, Activity.started_at))
        busiest = (
            await session.execute(
                self._rows(win, kinds, user, local_day, func.sum(Activity.watched_s), func.count())
                .group_by(local_day)
                .order_by(func.sum(Activity.watched_s).desc(), func.count().desc())
                .limit(1)
            )
        ).first()
        active_days = sorted(
            d
            for d in (
                await session.execute(self._rows(win, kinds, user, local_day).group_by(local_day))
            ).scalars()
            if isinstance(d, date)
        )
        streak = best = 0
        previous: date | None = None
        for day in active_days:
            streak = streak + 1 if previous is not None and (day - previous).days == 1 else 1
            best = max(best, streak)
            previous = day
        completed = await session.scalar(self._rows(win, kinds, user, func.count()).where(completed_clause()))
        first = await session.scalar(self._rows(win, kinds, user, func.min(Activity.started_at)))
        return {
            "longest": {
                "title": longest[0],
                "parent_title": longest[1],
                "seconds": float(longest[2]),
                "at": longest[3].isoformat(),
            }
            if longest
            else None,
            "busiest_day": {
                "date": busiest[0].isoformat(),
                "seconds": float(busiest[1] or 0),
                "plays": int(busiest[2]),
            }
            if busiest
            else None,
            "best_streak": best,
            "completed": int(completed or 0),
            "first_at": first.isoformat() if first else None,
        }

    async def _box_office(
        self, session: Any, win: Window, kinds: Sequence[str], user: UUID | None
    ) -> dict[str, Any] | None:
        if "movie" not in kinds:
            return None
        watched = (
            self._rows(win, ("movie",), user, Activity.work_id)
            .where(Activity.work_id.is_not(None))
            .group_by(Activity.work_id)
            .subquery()
        )
        budget = ObjectMetadata.data["budget"].as_float()
        revenue = ObjectMetadata.data["revenue"].as_float()
        row = (
            await session.execute(
                select(
                    func.count(),
                    func.coalesce(func.sum(budget), 0.0),
                    func.coalesce(func.sum(revenue), 0.0),
                    func.count().filter(budget > 0),
                ).where(ObjectMetadata.object_id == watched.c.work_id, ObjectMetadata.status == "found")
            )
        ).one()
        if not row[0] or not (row[1] or row[2]):  # no amounts known yet: nothing to tell
            return None
        top = (
            await session.execute(
                select(MediaObject.id, MediaObject.title, revenue)
                .join(ObjectMetadata, ObjectMetadata.object_id == MediaObject.id)
                .where(MediaObject.id.in_(select(watched.c.work_id)), revenue > 0)
                .order_by(revenue.desc())
                .limit(3)
            )
        ).all()
        return {
            "films": int(row[0]),
            "budget": float(row[1]),
            "revenue": float(row[2]),
            "with_budget": int(row[3]),
            "top": [{"id": str(i), "title": t, "revenue": float(r)} for i, t, r in top],
        }

    async def _platforms(
        self, session: Any, win: Window, kinds: Sequence[str], user: UUID | None
    ) -> list[dict[str, Any]]:
        name = func.coalesce(Activity.platform, Activity.device)
        rows = (
            await session.execute(
                self._rows(win, kinds, user, name, func.count(), func.sum(Activity.watched_s))
                .where(name.is_not(None))
                .group_by(name)
                .order_by(func.count().desc())
                .limit(8)
            )
        ).all()
        return [{"name": n, "plays": int(c), "seconds": float(s or 0)} for n, c, s in rows]

    async def _recent(
        self, session: Any, win: Window, kinds: Sequence[str], user: UUID | None
    ) -> list[dict[str, Any]]:
        rows = (
            await session.execute(
                self._rows(
                    win,
                    kinds,
                    user,
                    Activity.title,
                    Activity.parent_title,
                    Activity.kind,
                    Activity.work_id,
                    Activity.started_at,
                    Activity.watched_s,
                    Activity.progress,
                    Activity.user_id,
                    Activity.platform,
                )
                .order_by(Activity.started_at.desc())
                .limit(15)
            )
        ).all()
        return [
            {
                "title": title,
                "parent_title": parent,
                "kind": kind,
                "work_id": str(work) if work else None,
                "at": at.isoformat(),
                "seconds": float(seconds),
                "progress": progress,
                "user_id": str(member) if member and user is None else None,
                "platform": platform,
            }
            for title, parent, kind, work, at, seconds, progress, member, platform in rows
        ]

    async def _members(self, session: Any, win: Window, kinds: Sequence[str]) -> list[dict[str, Any]]:
        rows = (
            await session.execute(
                self._daily(
                    win,
                    kinds,
                    None,
                    ActivityDaily.user_key,
                    func.sum(ActivityDaily.plays),
                    func.sum(ActivityDaily.seconds),
                    func.sum(ActivityDaily.completed),
                    func.count(distinct(ActivityDaily.day)),
                    func.max(ActivityDaily.day),
                )
                .group_by(ActivityDaily.user_key)
                .order_by(func.sum(ActivityDaily.seconds).desc())
                .limit(50)
            )
        ).all()
        return [
            {
                "user_id": None if str(key) == NIL else str(key),
                "plays": int(plays),
                "seconds": float(seconds),
                "completed": int(completed),
                "active_days": int(days),
                "last_day": last.date().isoformat(),
            }
            for key, plays, seconds, completed, days, last in rows
        ]

    async def _requests(self, session: Any, win: Window, user: UUID | None) -> dict[str, Any]:
        query = select(MediaRequest.state, func.count()).where(MediaRequest.requested_at < win.end)
        if win.start is not None:
            query = query.where(MediaRequest.requested_at >= win.start)
        if user is not None:
            query = query.where(MediaRequest.requester_user_id == user)
        states = {
            state: int(count)
            for state, count in (await session.execute(query.group_by(MediaRequest.state))).all()
        }
        kind = MediaRequest.external_ref["kind"].astext
        by_kind = query.with_only_columns(kind, func.count()).group_by(kind)
        return {
            "total": sum(states.values()),
            "states": states,
            "kinds": {k or "other": int(n) for k, n in (await session.execute(by_kind)).all()},
            "available_rate": round(states.get("available", 0) / sum(states.values()), 3) if states else None,
        }
