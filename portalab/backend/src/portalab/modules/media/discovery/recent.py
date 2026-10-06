"""What is new in the library (027): « Recently added » — what the services added last (their own date:
Plex's ``addedAt``, Grimmory's ``addedOn``…), a new episode bringing its series up — and « Recent releases »
— what came out last (``released``: a film's or book's release date, an episode's air date). Both newest
first, one card per work, only what the library holds."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.modules.media.models import MediaObject, SourceItem

WORKS = ("movie", "series", "book", "audiobook", "game", "album")
UNITS = ("movie", "episode", "season", "series", "book", "audiobook", "game", "album", "track")


@dataclass(frozen=True, slots=True)
class Recent:
    object_id: UUID
    at: str  # ISO date (released) or instant (added)
    episode: str | None = None  # « S02E05 » when an episode brought its series up


async def _lineage(session: AsyncSession, ids: set[UUID]) -> dict[UUID, MediaObject]:
    """The objects and their ancestors (an episode, its season, its series)."""
    known: dict[UUID, MediaObject] = {}
    wanted = set(ids)
    for _ in range(3):
        missing = [i for i in wanted if i not in known]
        if not missing:
            break
        rows = (await session.execute(select(MediaObject).where(MediaObject.id.in_(missing)))).scalars()
        wanted = set()
        for row in rows:
            known[row.id] = row
            if row.parent_id is not None:
                wanted.add(row.parent_id)
    return known


def _work(object_id: UUID, known: dict[UUID, MediaObject]) -> tuple[MediaObject | None, str | None]:
    row = known.get(object_id)
    episode: str | None = None
    if row is not None and row.kind == "episode":
        season = known.get(row.parent_id) if row.parent_id else None
        if season is not None and season.position is not None and row.position is not None:
            episode = f"S{season.position:02d}E{row.position:02d}"
    while row is not None and row.parent_id is not None:
        row = known.get(row.parent_id)
    if row is None or row.kind not in WORKS or row.status != "active" or not row.available:
        return None, None
    return row, episode


async def _rank(
    session: AsyncSession, rows: Sequence[tuple[UUID, Any]], limit: int, kinds: Sequence[str] | None
) -> list[Recent]:
    known = await _lineage(session, {object_id for object_id, _ in rows})
    out: list[Recent] = []
    seen: set[UUID] = set()
    for object_id, at in rows:
        work, episode = _work(object_id, known)
        if work is None or work.id in seen or (kinds and work.kind not in kinds):
            continue
        seen.add(work.id)
        stamp = at.isoformat() if isinstance(at, datetime | date) else str(at)
        out.append(Recent(work.id, stamp, episode))
        if len(out) >= limit:
            break
    return out


async def recently_added(
    session: AsyncSession, *, limit: int = 16, kinds: Sequence[str] | None = None
) -> list[Recent]:
    rows = (
        await session.execute(
            select(SourceItem.object_id, SourceItem.observed_at)
            .where(
                SourceItem.object_id.is_not(None),
                SourceItem.availability == "available",
                SourceItem.kind.in_(UNITS),
            )
            .order_by(SourceItem.observed_at.desc())
            .limit(limit * 25)
        )
    ).all()
    return await _rank(session, [(r[0], r[1]) for r in rows], limit, kinds)


async def recent_releases(
    session: AsyncSession, today: date, *, limit: int = 16, kinds: Sequence[str] | None = None
) -> list[Recent]:
    released = SourceItem.payload["released"].astext
    rows = (
        await session.execute(
            select(SourceItem.object_id, released)
            .where(
                SourceItem.object_id.is_not(None),
                SourceItem.availability == "available",
                released.is_not(None),
                released <= today.isoformat(),
            )
            .order_by(released.desc())
            .limit(limit * 25)
        )
    ).all()
    return await _rank(session, [(r[0], str(r[1])[:10]) for r in rows], limit, kinds)
