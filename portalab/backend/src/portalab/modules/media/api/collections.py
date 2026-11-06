"""Issue 361: the collections of the library — a film's saga (TMDB's « collection »), a book's or an
audiobook's series, a game's franchise — told the same way on every title's page, and their own page.

``GET /media/{object_id}/collection``: the collection a title belongs to, with its other titles in the
library, in order (no service asked: what the library knows). ``GET /media/collection?ref=…``: the whole
collection — ``tmdb:<id>`` a saga, ``series:<name>`` a series or a franchise —, and for a saga every film
TMDB knows of it, each told available, asked for or missing (then where to ask for it). The reference is a
query parameter: a series' name may hold a slash."""

import logging
from collections import Counter
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from portalab.capabilities.media import METADATA, unwrap
from portalab.core.errors import NotFound
from portalab.modules.media.api.people import FilmCreditOut, _filmography
from portalab.modules.media.api.router import MediaCard, Module, Reader, _asked, _card
from portalab.modules.media.models import MediaObject, ObjectMetadata
from portalab.modules.media.permissions import MEDIA_REQUEST
from portalab.modules.media.providers.insight_widgets import posters

router = APIRouter(prefix="/api/v1", tags=["media"])
log = logging.getLogger(__name__)
LIMIT = 500
SAGA = "tmdb:"
SERIES = "series:"


class CollectionItemOut(MediaCard):
    position: float | None = None  # its volume in a series
    platform: str | None = None  # a game's: the same game may be there for several


class CollectionOut(BaseModel):
    ref: str  # ``tmdb:<id>`` (a film saga) or ``series:<name>`` (a book series, a game franchise)
    source: Literal["saga", "series"]
    name: str
    poster: str | None = None  # a saga's own poster, the provider's image (``/media/metadata-images``)
    items: list[CollectionItemOut]  # its titles in the library, in order
    parts: list[FilmCreditOut] = []  # the page of a saga: every film of it, in the library or not
    askable: bool = False  # the member may ask for the films missing


class CollectionNotFound(NotFound):
    default_code = "media.collection_not_found"
    default_title = "No such collection in the library"


def _position(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _order(row: MediaObject) -> tuple[Any, ...]:
    position = _position(row.effective.get("series_position"))
    return (position is None, position or 0, row.year is None, row.year or 0, row.sort_title, str(row.id))


async def _items(module: Module, rows: list[MediaObject]) -> list[CollectionItemOut]:
    rows = sorted(rows, key=_order)
    images = await posters(module.database, [row.id for row in rows])
    cards = await _asked(
        module, [_card(row, UUID(images[row.id]) if row.id in images else None) for row in rows]
    )
    return [
        CollectionItemOut(
            **card.model_dump(),
            position=_position(row.effective.get("series_position")),
            platform=str(row.effective["platform"])[:80] if row.effective.get("platform") else None,
        )
        for card, row in zip(cards, rows, strict=True)
    ]


async def _saga(module: Module, saga_id: str) -> tuple[str | None, str | None, list[MediaObject]]:
    """A saga's name and poster as the library's films tell them, and those films."""
    async with module.database.session() as session:
        found = (
            await session.execute(
                select(MediaObject, ObjectMetadata.data["collection"])
                .join(ObjectMetadata, ObjectMetadata.object_id == MediaObject.id)
                .where(
                    ObjectMetadata.status == "found",
                    ObjectMetadata.data["collection"]["id"].astext == saga_id,
                    MediaObject.status == "active",
                )
                .limit(LIMIT)
            )
        ).all()
    saga = next((c for _, c in found if isinstance(c, dict) and c.get("name")), None)
    return (
        str(saga["name"]) if saga else None,
        str(saga["poster"]) if saga and saga.get("poster") else None,
        [row for row, _ in found],
    )


async def _series(module: Module, name: str) -> tuple[str | None, list[MediaObject]]:
    """A series' (a franchise's) titles, whatever case they write its name in; its most common spelling."""
    async with module.database.session() as session:
        rows = list(
            (
                await session.execute(
                    select(MediaObject)
                    .where(
                        func.lower(MediaObject.effective["series"].astext) == name.strip().lower(),
                        MediaObject.status == "active",
                    )
                    .limit(LIMIT)
                )
            ).scalars()
        )
    spellings = Counter(str(row.effective["series"]) for row in rows)
    return (spellings.most_common(1)[0][0] if spellings else None), rows


async def _parts(module: Module, saga_id: str, language: str) -> list[FilmCreditOut] | None:
    """Every film of a saga as the metadata provider knows it (TMDB), with its standing in the library."""
    for registration in module.capabilities.system_providers(METADATA):
        saga = getattr(registration.provider, "saga", None)
        if saga is None:
            continue
        try:
            credits = unwrap(await saga(saga_id, language))
        except Exception as exc:
            log.info("saga lookup failed: %s: %s", type(exc).__name__, exc)
            return None  # the saga's page still shows the library's films
        if credits is None:
            return None
        parts = await _filmography(module, credits)
        parts.sort(key=lambda part: (part.year is None, part.year or 0, part.title))
        return parts
    return None


@router.get("/media/{object_id}/collection", response_model=CollectionOut | None)
async def title_collection(_: Reader, module: Module, object_id: UUID) -> CollectionOut | None:
    async with module.database.session() as session:
        row = await session.get(MediaObject, object_id)
        meta = await session.get(ObjectMetadata, object_id)
    if row is None or row.status != "active":
        return None
    collection = meta.data.get("collection") if meta is not None and meta.status == "found" else None
    if isinstance(collection, dict) and collection.get("id"):
        saga_id = str(collection["id"])
        name, poster, rows = await _saga(module, saga_id)
        return CollectionOut(
            ref=f"{SAGA}{saga_id}",
            source="saga",
            name=name or str(collection.get("name") or ""),
            poster=poster,
            items=await _items(module, rows),
        )
    series = row.effective.get("series")
    if isinstance(series, str) and series.strip():
        name, rows = await _series(module, series)
        return CollectionOut(
            ref=f"{SERIES}{name or series}",
            source="series",
            name=name or series,
            items=await _items(module, rows),
        )
    return None


@router.get("/media/collection", response_model=CollectionOut)
async def collection(
    principal: Reader, module: Module, ref: Annotated[str, Query(min_length=2, max_length=260)]
) -> CollectionOut:
    if ref.startswith(SAGA) and ref.removeprefix(SAGA).isdigit():
        saga_id = ref.removeprefix(SAGA)
        name, poster, rows = await _saga(module, saga_id)
        parts = await _parts(module, saga_id, await module.member_language(principal))
        if not rows and not parts:
            raise CollectionNotFound(f"no saga {saga_id}")
        askable = module.requestable.configured() and await module.authorizer.is_allowed(
            principal, MEDIA_REQUEST
        )
        return CollectionOut(
            ref=ref,
            source="saga",
            name=name or "",
            poster=poster,
            items=await _items(module, rows),
            parts=parts or [],
            askable=askable,
        )
    if ref.startswith(SERIES) and ref.removeprefix(SERIES).strip():
        name, rows = await _series(module, ref.removeprefix(SERIES)[:200])
        if not rows or name is None:
            raise CollectionNotFound(f"no series {ref[:60]!r}")
        return CollectionOut(
            ref=f"{SERIES}{name}", source="series", name=name, items=await _items(module, rows)
        )
    raise CollectionNotFound(f"no collection {ref[:60]!r}")
