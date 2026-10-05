"""What a member is in the middle of (027): their latest session of each title in the services' history
(Plex/Tautulli, Grimmory…) when it was started but not finished — films, episodes, books and audiobooks,
newest first. Live TV and finished titles are left out."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select

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
        "_lookup": (
            TMDB_KIND.get(row.kind, "movie"),
            dict(row.ids or {}),
            row.parent_title if series else row.title,
            row.year,
        ),
    }


async def in_progress(
    database: Database, user: UUID, now: datetime, *, limit: int = 8
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in await _latest(database, user, now):
        progress = progress_of(row)
        if progress is not None and not STARTED <= progress < FINISHED:
            continue  # finished (or barely started): not « continue »
        out.append(_item(row, progress))
        if len(out) >= limit:
            break
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
