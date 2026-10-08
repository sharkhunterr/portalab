"""Media statistics in depth (027, Telemetra-style): the sections behind the overview's tabs, each compared
with the previous period of the same length.

* ``casting`` — the directors (creators for series) and actors met most, with their portraits;
* ``production`` — what the films watched cost and earned (most expensive, cheapest, most profitable, budget
  ranges, financial successes and flops), their release years and production countries;
* ``playback`` — how they were played: direct play, direct stream or transcoded, in which resolution, on
  which players and platforms;
* ``profile`` — the genres (radar, new / rising / always / gone, by period), the activity curve, and the
  viewing footprint (hours of the day, days of the week).

Rows are the raw plays of the period (``counted`` only); metadata comes from the provider (TMDB). Device
names are only given where the overview gives them (« me », or media managers).
"""

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text

from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.media.insights.aggregate import COMPLETED
from portalab.modules.media.insights.stats import CATEGORIES, Window, window
from portalab.modules.media.models import Activity, MediaObject, ObjectMetadata, ObjectTag

SECTIONS = ("casting", "production", "playback", "profile")
STREAMS = ("direct", "copy", "transcode", "unknown")
QUALITIES = ("4k", "1080p", "720p", "sd", "unknown")
# budget ranges in millions of dollars: under 25, 25 to 75, 75 to 150, 150 to 250, 250 and more
BUDGET_RANGES: tuple[tuple[str, int, int | None], ...] = (
    ("<25", 0, 25),
    ("25-75", 25, 75),
    ("75-150", 75, 150),
    ("150-250", 150, 250),
    ("250+", 250, None),
)
# amounts under a million dollars are mostly provider mistakes (« 750 » meant 750 M): left out of the
# budget figures and the returns, so a typo never tops the « most profitable »
MIN_MONEY = 1_000_000
GENRE_SERIES = 8
PEOPLE = 10


@dataclass(frozen=True, slots=True)
class Bucket:
    start: datetime
    end: datetime

    @property
    def key(self) -> str:
        return self.start.date().isoformat()


def buckets(win: Window, first: datetime | None) -> tuple[str, list[Bucket]]:
    """Days for a month or less, weeks up to four months, else months: the window (or since ``first``)."""
    start = win.start or first or win.end - timedelta(days=30)
    days = (win.end - start).days
    unit = "day" if days <= 31 else ("week" if days <= 120 else "month")
    out: list[Bucket] = []
    if unit == "month":
        cursor = datetime(start.year, start.month, 1, tzinfo=UTC)
        while cursor < win.end:
            following = datetime(cursor.year + cursor.month // 12, cursor.month % 12 + 1, 1, tzinfo=UTC)
            out.append(Bucket(max(cursor, start), min(following, win.end)))
            cursor = following
    else:
        step = timedelta(days=1 if unit == "day" else 7)
        cursor = start
        while cursor < win.end:
            out.append(Bucket(cursor, min(cursor + step, win.end)))
            cursor += step
    return unit, out


def _index(at: datetime, slots: Sequence[Bucket], shift: timedelta = timedelta(0)) -> int | None:
    moved = at + shift
    for i, slot in enumerate(slots):
        if slot.start <= moved < slot.end:
            return i
    return None


def _completed(progress: float | None, watched: float, duration: float | None) -> bool:
    if progress is not None:
        return progress >= COMPLETED
    return bool(duration and duration > 0 and watched >= duration * COMPLETED)


class DeepInsights:
    def __init__(self, database: Database, *, clock: Clock | None = None) -> None:
        self.database = database
        self.clock = clock

    async def section(
        self,
        name: str,
        *,
        period: str,
        category: str,
        user: UUID | None,
        detailed: bool,
        tz: str = "UTC",
    ) -> dict[str, Any]:
        win = window(period, utc_now(self.clock))
        kinds = CATEGORIES.get(category, CATEGORIES["all"])
        before = win.previous()
        rows = await self._rows(win, kinds, user)
        previous = await self._rows(before, kinds, user) if before else []
        first = min((r["at"] for r in rows), default=None)
        unit, slots = buckets(win, first)
        shift = (win.end - before.end) if before else timedelta(0)
        common = {
            "section": name,
            "period": {"key": win.key, "start": win.start.isoformat() if win.start else None},
            "unit": unit,
            "buckets": [slot.key for slot in slots],
            "has_previous": before is not None,
        }
        if name == "casting":
            return {**common, **await self._casting(rows, previous)}
        if name == "production":
            return {**common, **await self._production(rows, previous, slots, shift, movies="movie" in kinds)}
        if name == "playback":
            return {**common, **self._playback(rows, previous, slots, shift, detailed)}
        return {**common, **await self._profile(rows, previous, slots, shift, ZoneInfo(tz))}

    async def _rows(self, win: Window, kinds: Sequence[str], user: UUID | None) -> list[dict[str, Any]]:
        query = select(
            Activity.started_at,
            Activity.work_id,
            Activity.kind,
            Activity.watched_s,
            Activity.duration_s,
            Activity.progress,
            Activity.stream,
            # the resolution played, else the file's (the library tells it when the source does not)
            func.coalesce(Activity.quality, MediaObject.effective["resolution"].astext),
            Activity.device,
            Activity.platform,
        )
        query = query.outerjoin(MediaObject, MediaObject.id == Activity.object_id).where(
            Activity.counted.is_(True), Activity.kind.in_(kinds), Activity.started_at < win.end
        )
        if win.start is not None:
            query = query.where(Activity.started_at >= win.start)
        if user is not None:
            query = query.where(Activity.user_id == user)
        async with self.database.session() as session:
            result = await session.execute(query)
            return [
                {
                    "at": at,
                    "work": work,
                    "kind": kind,
                    "seconds": float(watched or 0),
                    "completed": _completed(progress, float(watched or 0), duration),
                    "stream": stream,
                    "quality": quality,
                    "device": device,
                    "platform": platform,
                }
                for at, work, kind, watched, duration, progress, stream, quality, device, platform in result
            ]

    async def _metadata(self, works: Iterable[UUID]) -> dict[UUID, dict[str, Any]]:
        wanted = list({w for w in works if w is not None})
        if not wanted:
            return {}
        out: dict[UUID, dict[str, Any]] = {}
        async with self.database.session() as session:
            for chunk in range(0, len(wanted), 500):
                result = await session.execute(
                    select(ObjectMetadata.object_id, ObjectMetadata.data).where(
                        ObjectMetadata.object_id.in_(wanted[chunk : chunk + 500]),
                        ObjectMetadata.status == "found",
                    )
                )
                out.update({object_id: data for object_id, data in result.all()})
        return out

    async def _genres(self, works: Iterable[UUID]) -> dict[UUID, list[str]]:
        wanted = list({w for w in works if w is not None})
        out: dict[UUID, list[str]] = defaultdict(list)
        if not wanted:
            return out
        async with self.database.session() as session:
            for chunk in range(0, len(wanted), 500):
                result = await session.execute(
                    select(ObjectTag.object_id, ObjectTag.value).where(
                        ObjectTag.object_id.in_(wanted[chunk : chunk + 500]), ObjectTag.tag_kind == "genre"
                    )
                )
                for object_id, value in result.all():
                    out[object_id].append(value)
        return out

    # --- casting ------------------------------------------------------------------------------------

    async def _casting(self, rows: list[dict[str, Any]], previous: list[dict[str, Any]]) -> dict[str, Any]:
        seconds: Counter[UUID] = Counter()
        for row in rows:
            if row["work"] is not None:
                seconds[row["work"]] += row["seconds"]
        metadata = await self._metadata(seconds)
        before = {r["work"] for r in previous if r["work"] is not None}
        before_meta = await self._metadata(before - set(seconds))
        before_meta.update({k: v for k, v in metadata.items() if k in before})

        def tally(meta: dict[UUID, dict[str, Any]], directing: bool) -> dict[str, dict[str, Any]]:
            people: dict[str, dict[str, Any]] = {}
            for work, data in meta.items():
                cast_seen = 0
                for person in data.get("people") or []:
                    department = str(person.get("department") or "")
                    role = str(person.get("role") or "")
                    if directing:
                        wanted = (department == "directing" and role == "Director") or department == "creator"
                    else:
                        wanted = department == "cast" and cast_seen < 15  # the top-billed cast
                        cast_seen += department == "cast"
                    name = str(person.get("name") or "")
                    if not wanted or not name:
                        continue
                    key = str((person.get("ids") or {}).get("tmdb") or name)
                    entry = people.setdefault(
                        key, {"name": name, "image": person.get("image"), "works": set(), "seconds": 0.0}
                    )
                    if work not in entry["works"]:
                        entry["works"].add(work)
                        entry["seconds"] += seconds.get(work, 0.0)
                    entry["image"] = entry["image"] or person.get("image")
            return people

        def ranked(directing: bool) -> list[dict[str, Any]]:
            now, then = tally(metadata, directing), tally(before_meta, directing)
            top = sorted(now.items(), key=lambda kv: (-len(kv[1]["works"]), -kv[1]["seconds"], kv[1]["name"]))
            return [
                {
                    "name": entry["name"],
                    "image": entry["image"],
                    "works": len(entry["works"]),
                    "seconds": round(entry["seconds"]),
                    "previous": len(then[key]["works"]) if key in then else 0,
                    "titles": [str(metadata[w].get("title") or "") for w in list(entry["works"])[:4]],
                }
                for key, entry in top[:PEOPLE]
            ]

        return {"directors": ranked(True), "actors": ranked(False), "with_metadata": len(metadata)}

    # --- production ---------------------------------------------------------------------------------

    async def _production(
        self,
        rows: list[dict[str, Any]],
        previous: list[dict[str, Any]],
        slots: Sequence[Bucket],
        shift: timedelta,
        *,
        movies: bool,
    ) -> dict[str, Any]:
        now_works = {r["work"] for r in rows if r["work"] is not None}
        then_works = {r["work"] for r in previous if r["work"] is not None}
        meta = await self._metadata(now_works | then_works)

        def films(works: set[UUID]) -> list[dict[str, Any]]:
            out = []
            for work in works:
                data = meta.get(work)
                if not data:
                    continue
                budget, revenue = int(data.get("budget") or 0), int(data.get("revenue") or 0)
                budget = budget if budget >= MIN_MONEY else 0
                revenue = revenue if revenue >= MIN_MONEY else 0
                year = str(data.get("release_date") or "")[:4]
                out.append(
                    {
                        "id": str(work),
                        "title": str(data.get("title") or ""),
                        "poster_ref": data.get("poster"),
                        "budget": budget or None,
                        "revenue": revenue or None,
                        "roi": round(revenue / budget, 2) if budget > 0 and revenue > 0 else None,
                        "year": int(year) if year.isdigit() else None,
                        "countries": [str(c) for c in data.get("countries") or []][:6],
                    }
                )
            return out

        now, then = films(now_works), films(then_works)
        years_now = Counter(f["year"] for f in now if f["year"])
        years_then = Counter(f["year"] for f in then if f["year"])

        def average(counter: Counter[int]) -> float | None:
            total = sum(counter.values())
            return round(sum(y * n for y, n in counter.items()) / total, 1) if total else None

        countries: Counter[str] = Counter(c for f in now for c in f["countries"])
        result: dict[str, Any] = {
            "films": len(now),
            "years": [
                {"year": year, "count": years_now.get(year, 0), "previous": years_then.get(year, 0)}
                for year in sorted(set(years_now) | set(years_then))
            ],
            "year_average": average(years_now),
            "year_average_previous": average(years_then),
            "countries": [{"code": code, "count": n} for code, n in countries.most_common()],
        }
        if not movies:
            return result
        budgeted = [f for f in now if f["budget"]]
        profitable = [f for f in now if f["roi"] is not None]

        def ranges(items: list[dict[str, Any]]) -> Counter[str]:
            out: Counter[str] = Counter()
            for film in items:
                millions = film["budget"] / 1_000_000
                for label, low, high in BUDGET_RANGES:
                    if millions >= low and (high is None or millions < high):
                        out[label] += 1
                        break
            return out

        budgets_now, budgets_then = ranges(budgeted), ranges([f for f in then if f["budget"]])
        by_budget = sorted(budgeted, key=lambda f: int(f["budget"]))
        by_roi = sorted(profitable, key=lambda f: float(f["roi"]))
        result.update(
            {
                "most_expensive": by_budget[-1] if by_budget else None,
                "cheapest": by_budget[0] if by_budget else None,
                "most_profitable": by_roi[-1] if by_roi else None,
                "budget_average": round(sum(f["budget"] for f in budgeted) / len(budgeted))
                if budgeted
                else None,
                "budgets": [
                    {
                        "range": label,
                        "count": budgets_now.get(label, 0),
                        "previous": budgets_then.get(label, 0),
                    }
                    for label, _low, _high in BUDGET_RANGES
                ],
                "successes": by_roi[::-1][:5],
                "flops": by_roi[:5],
                "revenue_total": sum(f["revenue"] or 0 for f in now),
                "budget_total": sum(f["budget"] or 0 for f in now),
            }
        )
        return result

    # --- playback -----------------------------------------------------------------------------------

    def _playback(
        self,
        rows: list[dict[str, Any]],
        previous: list[dict[str, Any]],
        slots: Sequence[Bucket],
        shift: timedelta,
        detailed: bool,
    ) -> dict[str, Any]:
        def series(field: str, keys: Sequence[str]) -> dict[str, Any]:
            now: Counter[str] = Counter(r[field] or "unknown" for r in rows)
            then: Counter[str] = Counter(r[field] or "unknown" for r in previous)
            current: list[Counter[str]] = [Counter() for _ in slots]
            past: list[Counter[str]] = [Counter() for _ in slots]
            for row in rows:
                i = _index(row["at"], slots)
                if i is not None:
                    current[i][row[field] or "unknown"] += 1
            for row in previous:
                i = _index(row["at"], slots, shift)
                if i is not None:
                    past[i][row[field] or "unknown"] += 1
            order = [k for k in keys if now.get(k) or then.get(k)]
            return {
                "totals": [{"key": k, "count": now.get(k, 0), "previous": then.get(k, 0)} for k in order],
                "series": [
                    {"current": dict(current[i]), "previous": dict(past[i])} for i in range(len(slots))
                ],
            }

        def top(field: str) -> list[dict[str, Any]]:
            counts: Counter[str] = Counter(r[field] for r in rows if r[field])
            return [{"name": name, "count": n} for name, n in counts.most_common(6)]

        return {
            "total": len(rows),
            "total_previous": len(previous),
            "streams": series("stream", STREAMS),
            "qualities": series("quality", QUALITIES),
            "platforms": top("platform"),
            "devices": top("device") if detailed else None,
        }

    # --- profile ------------------------------------------------------------------------------------

    async def _profile(
        self,
        rows: list[dict[str, Any]],
        previous: list[dict[str, Any]],
        slots: Sequence[Bucket],
        shift: timedelta,
        zone: ZoneInfo,
    ) -> dict[str, Any]:
        genres = await self._genres({r["work"] for r in rows} | {r["work"] for r in previous})
        now: Counter[str] = Counter(g for r in rows for g in genres.get(r["work"], ()))
        then: Counter[str] = Counter(g for r in previous for g in genres.get(r["work"], ()))
        names = sorted(set(now) | set(then), key=lambda g: (-now.get(g, 0), -then.get(g, 0), g))
        summary: dict[str, list[str]] = {"new": [], "rising": [], "always": [], "gone": []}
        for name in names:
            a, b = now.get(name, 0), then.get(name, 0)
            if a and not b:
                summary["new"].append(name)
            elif b and not a:
                summary["gone"].append(name)
            else:
                summary["always"].append(name)
                if a > b * 1.1:
                    summary["rising"].append(name)
        main = [g for g in names if now.get(g)][:GENRE_SERIES]
        stacked: list[Counter[str]] = [Counter() for _ in slots]
        activity = [[0, 0] for _ in slots]  # plays then completed plays, by bucket
        activity_previous = [[0, 0] for _ in slots]
        for row in rows:
            i = _index(row["at"], slots)
            if i is None:
                continue
            activity[i][0] += 1
            activity[i][1] += int(row["completed"])
            for genre in genres.get(row["work"], ()):
                stacked[i][genre if genre in main else "other"] += 1
        for row in previous:
            i = _index(row["at"], slots, shift)
            if i is not None:
                activity_previous[i][0] += 1
                activity_previous[i][1] += int(row["completed"])
        hours = [0] * 24
        weekdays = [0] * 7
        for row in rows:
            local = row["at"].astimezone(zone)
            hours[local.hour] += 1
            weekdays[local.isoweekday() - 1] += 1
        return {
            "genres": [{"name": g, "count": now.get(g, 0), "previous": then.get(g, 0)} for g in names[:14]],
            "summary": summary,
            "genre_series": main,
            "genre_buckets": [dict(c) for c in stacked],
            "activity": [
                {"plays": a[0], "completed": a[1], "previous_plays": p[0], "previous_completed": p[1]}
                for a, p in zip(activity, activity_previous, strict=True)
            ],
            "hours": hours,
            "weekdays": weekdays,
        }


async def portraits(database: Database, names: Sequence[str]) -> dict[str, str]:
    """027: a portrait for each person named (the metadata provider's image, from any title they are in)."""
    if not names:
        return {}
    query = text(
        "SELECT DISTINCT ON (p->>'name') p->>'name', p->>'image' "
        "FROM media.object_metadata m, jsonb_array_elements(m.data->'people') p "
        "WHERE m.status = 'found' AND p->>'name' = ANY(:names) AND coalesce(p->>'image', '') <> '' "
        "ORDER BY p->>'name'"
    )
    async with database.session() as session:
        rows = await session.execute(query, {"names": list(names)})
        return {str(name): str(image) for name, image in rows.all()}
