"""What a member is in the middle of (027): their latest session of each title in the services' history
(Plex/Tautulli, Grimmory…) when it was started but not finished — films, episodes, books and audiobooks,
newest first — and (#190) the games played in RomM. Live TV and finished titles are left out."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.media import ResumePoint
from portalab.core.db import Database
from portalab.modules.media.models import Activity

DAYS = 90
STARTED, FINISHED = 0.03, 0.92
TMDB_KIND = {"movie": "movie", "episode": "series", "book": "book", "audiobook": "audiobook"}


def progress_of(row: Activity) -> float | None:
    if row.progress is not None:
        return float(row.progress)
    if row.duration_s:
        return min(1.0, float(row.watched_s or 0) / float(row.duration_s))
    return None


async def _latest(database: Database, user: UUID, now: datetime) -> list[Activity]:
    """The latest session of each title the member opened lately, newest first (live TV left out)."""
    async with database.session() as session:
        rows = (
            (
                await session.execute(
                    select(Activity)
                    .where(
                        Activity.user_id == user,
                        Activity.started_at >= now - timedelta(days=DAYS),
                        Activity.kind != "live",
                    )
                    .order_by(Activity.started_at.desc())
                    .limit(500)
                )
            )
            .scalars()
            .all()
        )
    seen: set[Any] = set()
    out: list[Activity] = []
    for row in rows:
        key = row.object_id or (row.kind, row.parent_title, row.title)
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out


def _item(row: Activity, progress: float | None) -> dict[str, Any]:
    series = row.kind == "episode" and row.parent_title
    return {
        "id": str(row.object_id) if row.object_id else None,
        "title": row.parent_title if series else row.title,
        "subtitle": row.title if series else row.parent_title,
        "kind": row.kind,
        "progress": progress,
        "meta": f"{round(progress * 100)} %" if progress is not None else None,
        "at": row.started_at.isoformat(),
        # #190: a game is never looked for among films (« Alien Resurrection » the game is not the film)
        "_lookup": None
        if row.kind == "game"
        else (
            TMDB_KIND.get(row.kind, "movie"),
            dict(row.ids or {}),
            row.parent_title if series else row.title,
            row.year,
        ),
    }


def resume_item(point: ResumePoint, object_id: UUID | None) -> dict[str, Any]:
    """027 (#23): a card from a server's own « Continue watching » (a position, or the next episode)."""
    series = point.kind == "episode" and point.parent_title
    progress = (
        min(1.0, point.position_s / point.duration_s) if point.position_s and point.duration_s else None
    )
    episode = f"{point.label} · {point.title}" if point.label else point.title
    return {
        "id": str(object_id) if object_id else None,
        "title": point.parent_title if series else point.title,
        "subtitle": episode if series else None,
        "kind": point.kind,
        "progress": progress,
        "meta": f"{round(progress * 100)} %" if progress is not None else point.label,
        "at": point.at.isoformat() if point.at else None,
        "_lookup": (
            TMDB_KIND.get(point.kind, "movie"),
            dict(point.ids or {}),
            point.parent_title if series else point.title,
            point.year,
        ),
    }


def _key(item: dict[str, Any]) -> Any:
    return item.get("id") or (item.get("kind"), item.get("title"))


async def in_progress(
    database: Database,
    user: UUID,
    now: datetime,
    *,
    limit: int = 8,
    live: list[dict[str, Any]] | None = None,
    skip_families: set[str] | frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    """``live``: the servers' own « Continue watching » first (#23); their history families are then left
    out, so a title finished or set back to zero there leaves the shelf too."""
    out: list[dict[str, Any]] = list(live or [])[:limit]
    keys = {_key(item) for item in out}
    for row in await _latest(database, user, now):
        if len(out) >= limit:
            break
        if row.family and row.family in skip_families:
            continue
        progress = progress_of(row)
        if progress is not None and not STARTED <= progress < FINISHED:
            continue  # finished (or barely started): not « continue »
        item = _item(row, progress)
        if _key(item) in keys:
            continue
        keys.add(_key(item))
        out.append(item)
    return out


async def recently(database: Database, user: UUID, now: datetime, *, limit: int = 12) -> list[dict[str, Any]]:
    """What the member watched, read or listened to lately — one card per title (a series once)."""
    out: list[dict[str, Any]] = []
    shown: set[tuple[str, str]] = set()
    for row in await _latest(database, user, now):
        item = _item(row, progress_of(row))
        name = (str(item["kind"]), str(item["title"]))
        if name in shown:
            continue  # several episodes of one series: the series once
        shown.add(name)
        out.append(item)
        if len(out) >= limit:
            break
    return out
