"""Catalog read side (T014): browse with filters (kind, genre, year, availability, text) and cursor
pagination, one object with its ids, children and poster, and the ``media.catalog`` port for other
modules. Merged objects resolve to their survivor; hidden ones are only shown to ``media.manage``."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select

from portalab.capabilities.media_core import MediaSummary
from portalab.capabilities.search.fts import decode_cursor, encode_cursor
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.modules.media.common import normalize_title, strong_ids
from portalab.modules.media.identity.resolver import MediaNotFound, live_object
from portalab.modules.media.models import ExternalId, Image, MediaObject, ObjectTag
from portalab.modules.media.permissions import MEDIA_MANAGE, MEDIA_READ

PAGE = 48


@dataclass(frozen=True, slots=True)
class ObjectView:
    id: UUID
    kind: str
    title: str
    year: int | None
    available: bool
    status: str
    parent_id: UUID | None
    position: int | None
    image_id: UUID | None
    effective: dict[str, Any]
    ids: dict[str, str] = field(default_factory=dict)
    children: list[dict[str, Any]] = field(default_factory=list)
    first_seen_at: datetime | None = None


def summary(row: MediaObject) -> MediaSummary:
    return MediaSummary(
        id=row.id,
        kind=row.kind,
        title=row.title,
        year=row.year,
        available=row.available,
        route=f"/media/{row.id}",
        genres=tuple(str(g) for g in (row.effective or {}).get("genres") or ()),
    )


class CatalogQuery:
    def __init__(self, database: Database, authorizer: Authorizer) -> None:
        self.database = database
        self.authorizer = authorizer

    async def _can(self, principal: Principal, permission: str) -> bool:
        try:
            return await self.authorizer.is_allowed(principal, permission)
        except Exception:
            return False

    async def browse(
        self,
        principal: Principal,
        *,
        kind: str | None = None,
        genre: str | None = None,
        year: int | None = None,
        availability: str | None = None,
        q: str | None = None,
        top_level: bool = True,
        cursor: str | None = None,
        limit: int = PAGE,
    ) -> tuple[list[tuple[MediaObject, UUID | None]], str | None]:
        statuses = ("active", "hidden") if await self._can(principal, MEDIA_MANAGE) else ("active",)
        stmt = select(MediaObject).where(MediaObject.status.in_(statuses))
        if kind:
            stmt = stmt.where(MediaObject.kind == kind)
        elif top_level:
            stmt = stmt.where(MediaObject.parent_id.is_(None))
        if year is not None:
            stmt = stmt.where(MediaObject.year == year)
        if availability in ("available", "unavailable"):
            stmt = stmt.where(MediaObject.available.is_(availability == "available"))
        if genre:
            stmt = stmt.where(
                MediaObject.id.in_(
                    select(ObjectTag.object_id).where(
                        ObjectTag.tag_kind == "genre", func.lower(ObjectTag.value) == genre.strip().lower()
                    )
                )
            )
        if q:
            words = normalize_title(q).split()[:8]
            if words:
                stmt = stmt.where(and_(*(MediaObject.sort_title.ilike(f"%{w}%") for w in words)))
        offset = decode_cursor(cursor)
        limit = max(1, min(limit, 100))
        stmt = stmt.order_by(MediaObject.sort_title, MediaObject.id).offset(offset).limit(limit + 1)
        async with self.database.session() as session:
            rows = list((await session.execute(stmt)).scalars().all())
            images = await self._images(session, [r.id for r in rows[:limit]])
        page = [(row, images.get(row.id)) for row in rows[:limit]]
        return page, encode_cursor(offset + limit) if len(rows) > limit else None

    @staticmethod
    async def _images(session: Any, ids: Sequence[UUID]) -> dict[UUID, UUID]:
        if not ids:
            return {}
        rows = await session.execute(
            select(Image.object_id, Image.id).where(Image.object_id.in_(list(ids)), Image.role == "poster")
        )
        return {object_id: image_id for object_id, image_id in rows}

    async def get(self, principal: Principal, object_id: UUID) -> ObjectView:
        async with self.database.session() as session:
            row = await live_object(session, object_id)
            if row is None or (row.status == "hidden" and not await self._can(principal, MEDIA_MANAGE)):
                raise MediaNotFound("This object does not exist.")
            ids = {
                scheme: value
                for scheme, value in await session.execute(
                    select(ExternalId.scheme, ExternalId.value).where(ExternalId.object_id == row.id)
                )
            }
            children = (
                (
                    await session.execute(
                        select(MediaObject)
                        .where(MediaObject.parent_id == row.id, MediaObject.status == "active")
                        .order_by(MediaObject.position, MediaObject.sort_title)
                        .limit(500)
                    )
                )
                .scalars()
                .all()
            )
            images = await self._images(session, [row.id])
        return ObjectView(
            id=row.id,
            kind=row.kind,
            title=row.title,
            year=row.year,
            available=row.available,
            status=row.status,
            parent_id=row.parent_id,
            position=row.position,
            image_id=images.get(row.id),
            effective=dict(row.effective or {}),
            ids=ids,
            children=[
                {
                    "id": str(c.id),
                    "kind": c.kind,
                    "title": c.title,
                    "position": c.position,
                    "available": c.available,
                }
                for c in children
            ],
            first_seen_at=row.first_seen_at,
        )


class CatalogPort:
    """``media.catalog`` for other modules (Community, AI, Statistics…): permission-bounded lookups."""

    def __init__(self, query: CatalogQuery) -> None:
        self.query = query

    async def get(self, object_id: UUID, viewer: Principal) -> MediaSummary | None:
        if not await self.query._can(viewer, MEDIA_READ):
            return None
        async with self.query.database.session() as session:
            row = await live_object(session, object_id)
        if row is None or row.status != "active":
            return None
        return summary(row)

    async def resolve_ref(self, ref: str, viewer: Principal) -> MediaSummary | None:
        scheme, _, value = ref.partition(":")
        if scheme == "media":
            try:
                return await self.get(UUID(value), viewer)
            except ValueError:
                return None
        ids = strong_ids({scheme: value})
        if not ids:
            return None
        async with self.query.database.session() as session:
            found = await session.scalar(
                select(ExternalId.object_id).where(
                    or_(*(and_(ExternalId.scheme == s, ExternalId.value == v) for s, v in ids.items()))
                )
            )
        return await self.get(found, viewer) if found is not None else None
