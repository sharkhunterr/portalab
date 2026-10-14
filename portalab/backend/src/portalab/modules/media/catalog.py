"""Catalog read side (T014): browse with filters (kind, genre, year, availability, text) and cursor
pagination, one object with its ids, children and poster, and the ``media.catalog`` port for other
modules. Merged objects resolve to their survivor; hidden ones are only shown to ``media.manage``."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, case, func, literal, literal_column, not_, or_, select, union
from sqlalchemy.orm import aliased

from portalab.capabilities.media_core import MediaSummary
from portalab.capabilities.search.fts import decode_cursor, encode_cursor
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.modules.media.common import strong_ids
from portalab.modules.media.identity.resolver import MediaNotFound, live_object
from portalab.modules.media.matching import matching, words
from portalab.modules.media.models import ExternalId, Image, MediaObject, ObjectTag, UserProgress
from portalab.modules.media.permissions import MEDIA_MANAGE, MEDIA_READ

PAGE = 48
FACET_SIZE = 300
# #111: the filters a kind has besides genre and year — a member's name for each, and the field it reads
FACETS: dict[str, tuple[tuple[str, str], ...]] = {
    "movie": (("directors", "directors"),),
    "series": (("directors", "directors"),),
    "book": (
        ("authors", "authors"),
        ("series", "series"),
        ("languages", "language"),
        ("publishers", "publisher"),
    ),
    "audiobook": (
        ("authors", "authors"),
        ("narrators", "narrators"),
        ("series", "series"),
        ("languages", "language"),
    ),
    "game": (("platforms", "platform"), ("publishers", "publisher")),
}
REFINE_FIELDS = {
    "author": "authors",
    "narrator": "narrators",
    "director": "directors",
    "platform": "platform",
    "publisher": "publisher",
    "series": "series",
    "language": "language",
}
SORTS = ("title", "added", "year")
SEEN = ("unseen", "started", "finished")


PARTIAL = {"author", "narrator", "director", "series", "publisher"}  # typed in: part of a name will do


def _field_matches(name: str, value: str, *, partial: bool = False) -> Any:
    """A metadata field naming ``value`` — a list containing it (authors…) or the value itself (platform…),
    whatever its case; ``partial``: a name containing it (« herbert » finds Frank Herbert)."""
    field = MediaObject.effective[name]
    wanted = value.strip().lower()

    def test(text: Any) -> Any:
        return func.lower(text).contains(wanted, autoescape=True) if partial else func.lower(text) == wanted

    as_list = func.jsonb_typeof(field) == "array"
    contains = (
        select(literal(1))
        .select_from(func.jsonb_array_elements_text(field).alias("item"))
        .where(test(literal_column("item")))
        .exists()
    )
    return or_(and_(as_list, contains), and_(not_(as_list), test(field.astext)))


async def _values(session: Any, name: str, scope: list[Any]) -> list[str]:
    field = MediaObject.effective[name]
    item = func.jsonb_array_elements_text(
        case((func.jsonb_typeof(field) == "array", field), else_=func.jsonb_build_array(field))
    ).alias("item")
    value: Any = literal_column("item")
    rows = await session.execute(
        select(func.min(value), func.count())
        .select_from(MediaObject)
        .join(item, literal(True))
        .where(*scope, field.is_not(None), func.length(value) > 0)
        .group_by(func.lower(value))
        .order_by(func.count().desc(), func.min(value))
        .limit(FACET_SIZE)
    )
    return [str(v) for v, _ in rows.all()]


@dataclass(frozen=True, slots=True)
class Refine:
    """#111: the catalog's finer filters — a span of years, a person or a platform, what the member has
    already watched, read or played (or not), and the order."""

    year_from: int | None = None
    year_to: int | None = None
    fields: dict[str, str] = field(default_factory=dict)  # author, narrator, director, platform…
    seen: str | None = None  # unseen, started, finished — the member's own progress
    sort: str = "title"

    def apply(self, stmt: Any, user: UUID | None) -> Any:
        if self.year_from is not None:
            stmt = stmt.where(MediaObject.year >= self.year_from)
        if self.year_to is not None:
            stmt = stmt.where(MediaObject.year <= self.year_to)
        for key, value in self.fields.items():
            if key in REFINE_FIELDS and value.strip():
                stmt = stmt.where(_field_matches(REFINE_FIELDS[key], value, partial=key in PARTIAL))
        if self.seen in SEEN and user is not None:
            stmt = stmt.where(_seen(user, self.seen))
        return stmt

    def order(self) -> tuple[Any, ...]:
        if self.sort == "added":
            return (MediaObject.first_seen_at.desc(), MediaObject.id)
        if self.sort == "year":
            return (MediaObject.year.desc().nulls_last(), MediaObject.sort_title, MediaObject.id)
        return (MediaObject.sort_title, MediaObject.id)


def _seen(user: UUID, seen: str) -> Any:
    """A title the member started or finished — itself, or one of its episodes or seasons (a series is
    « started » from its first episode; « finished » once one of them is)."""
    progress = select(UserProgress.object_id).where(UserProgress.user_id == user)
    if seen == "unseen":
        return MediaObject.id.not_in(_with_parents(progress))
    return MediaObject.id.in_(
        _with_parents(
            progress.where(UserProgress.state == ("finished" if seen == "finished" else "in_progress"))
        )
    )


def _with_parents(progress: Any) -> Any:
    """The titles with some progress, their seasons and their series."""
    touched = aliased(MediaObject)
    parent = aliased(MediaObject)
    ids: Any = select(touched.id).where(touched.id.in_(progress))
    parents: Any = select(touched.parent_id).where(touched.id.in_(progress), touched.parent_id.is_not(None))
    grandparents: Any = (
        select(parent.parent_id)
        .join(touched, touched.parent_id == parent.id)
        .where(touched.id.in_(progress), parent.parent_id.is_not(None))
    )
    return union(ids, parents, grandparents)


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
        refine: Refine | None = None,
    ) -> tuple[list[tuple[MediaObject, UUID | None]], str | None]:
        page, next_cursor, _ = await self.search(
            principal,
            kind=kind,
            genre=genre,
            year=year,
            availability=availability,
            q=q,
            top_level=top_level,
            cursor=cursor,
            limit=limit,
            refine=refine,
        )
        return page, next_cursor

    async def search(
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
        refine: Refine | None = None,
    ) -> tuple[list[tuple[MediaObject, UUID | None]], str | None, int]:
        """The catalog's page under the filters, and how many titles match them in all (#111)."""
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
        if q and (found := words(q)):
            stmt = stmt.where(matching(found))  # #92: its people and series too, typos forgiven
        refine = refine or Refine()
        stmt = refine.apply(stmt, principal.acting_for or principal.user_id)
        offset = decode_cursor(cursor)
        limit = max(1, min(limit, 100))
        async with self.database.session() as session:
            total = int(await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
            ordered = stmt.order_by(*refine.order()).offset(offset).limit(limit + 1)
            rows = list((await session.execute(ordered)).scalars().all())
            images = await self._images(session, [r.id for r in rows[:limit]])
        page = [(row, images.get(row.id)) for row in rows[:limit]]
        return page, encode_cursor(offset + limit) if len(rows) > limit else None, total

    async def facets(self, principal: Principal, kind: str | None) -> dict[str, Any]:
        """#111: what the catalog's filters can offer for a kind — its genres, its years, and the people,
        platforms, publishers, series or languages its titles name, the most common first."""
        statuses = ("active", "hidden") if await self._can(principal, MEDIA_MANAGE) else ("active",)
        scope: list[Any] = [
            MediaObject.status.in_(statuses),
            MediaObject.kind == kind if kind else MediaObject.parent_id.is_(None),
        ]
        out: dict[str, Any] = {}
        async with self.database.session() as session:
            low, high = (
                await session.execute(
                    select(func.min(MediaObject.year), func.max(MediaObject.year)).where(*scope)
                )
            ).one()
            out["years"] = {"min": low, "max": high}
            genre = func.lower(ObjectTag.value)
            out["genres"] = [
                value
                for value, _ in (
                    await session.execute(
                        select(func.min(ObjectTag.value), func.count())
                        .join(MediaObject, MediaObject.id == ObjectTag.object_id)
                        .where(ObjectTag.tag_kind == "genre", *scope)
                        .group_by(genre)
                        .order_by(func.count().desc())
                        .limit(FACET_SIZE)
                    )
                ).all()
            ]
            for name, field_name in FACETS.get(kind or "", ()):
                out[name] = await _values(session, field_name, scope)
        return out

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
