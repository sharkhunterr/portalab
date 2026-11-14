"""032: what a household profile's age rating keeps from it. A profile its master restricted to an age (and,
maybe, to rated titles only) is never served a film or a series rated above it — nor the series' seasons and
episodes — from the catalog, the detail pages, the shelves, the search, the recommendations, the feed, the
dashboard widgets or the players, unless its master let it open that title (an approved access request).

Ratings are the metadata provider's (TMDB's ``certification``, stored with each film's and series' metadata);
other kinds (books, music, games, live TV) have no rating and are never held back. Members without a
restriction cost one cached lookup: nothing is computed for them."""

import time
from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import Any
from uuid import UUID

from sqlalchemy import Uuid, all_, literal, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import aliased

from portalab.capabilities.household import CAPABILITY as HOUSEHOLD
from portalab.capabilities.household import Household, Restrictions, genre_of, strictest_age
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.errors import Forbidden
from portalab.modules.media.models import MediaObject, ObjectMetadata, ObjectTag

RATED = ("movie", "series")
CACHE_S = 30.0
IDS = ("id", "object_id", "media_id", "work_id")


class Restricted(Forbidden):
    default_code = "household.restricted"
    default_title = "This title is not open to this profile"


def labelled(data: Mapping[str, Any] | None, server: str | None) -> list[tuple[str, str]]:
    """A title's age ratings by source: TMDB's countries (« FR », « US »…), else its single certification
    (details found before 032), and the media server's (« server »)."""
    data = data or {}
    found: list[tuple[str, str]] = []
    countries = data.get("certifications")
    if isinstance(countries, Mapping) and countries:
        found += [(str(c), str(r)) for c, r in countries.items() if r]
    elif data.get("certification"):
        found.append(("TMDB", str(data["certification"])))
    if server:
        found.append(("server", server))
    return found


def ratings(data: Mapping[str, Any] | None, server: str | None) -> list[str]:
    return [value for _, value in labelled(data, server)]


def excluded(column: Any, blocked: frozenset[UUID]) -> Any:
    """A clause keeping the rows whose ``column`` is none of the ``blocked`` titles (one array parameter,
    however many there are)."""
    return column != all_(literal(list(blocked), ARRAY(Uuid())))


def viewer_of(viewer: Principal | UUID | None) -> UUID | None:
    if isinstance(viewer, Principal):
        return viewer.acting_for or viewer.user_id
    return viewer


class TitleGate:
    def __init__(self, database: Database, capabilities: CapabilityRegistry) -> None:
        self.database = database
        self.capabilities = capabilities
        self._cache: dict[UUID, tuple[float, frozenset[UUID]]] = {}

    def _household(self) -> Household | None:
        providers = self.capabilities.system_providers(HOUSEHOLD)
        return providers[0].provider if providers else None

    async def restrictions(self, viewer: Principal | UUID | None) -> Restrictions | None:
        user, household = viewer_of(viewer), self._household()
        if user is None or household is None:
            return None
        restrictions = await household.restrictions_of(user)
        return restrictions if restrictions is not None and restrictions.limits_titles else None

    async def blocked(self, viewer: Principal | UUID | None) -> frozenset[UUID]:
        """The titles (and their seasons and episodes) kept from this viewer — empty for nearly everyone."""
        restrictions = await self.restrictions(viewer)
        user, household = viewer_of(viewer), self._household()
        if restrictions is None or user is None or household is None:
            return frozenset()
        cached = self._cache.get(user)
        if cached is not None and time.monotonic() - cached[0] < CACHE_S:
            return cached[1]
        granted = await household.grants(user, "media")
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(
                        MediaObject.id, ObjectMetadata.data, MediaObject.effective["content_rating"].astext
                    )
                    .outerjoin(
                        ObjectMetadata,
                        (ObjectMetadata.object_id == MediaObject.id) & (ObjectMetadata.status == "found"),
                    )
                    .where(MediaObject.kind.in_(RATED))
                )
            ).all()
            works = {
                work
                for work, data, server in rows
                if str(work) not in granted
                and not restrictions.allows_age(strictest_age(ratings(data, server)))
            }
            if restrictions.genres:  # kept out whatever their rating (horror…)
                tags = await session.execute(
                    select(ObjectTag.object_id, ObjectTag.value)
                    .join(MediaObject, MediaObject.id == ObjectTag.object_id)
                    .where(ObjectTag.tag_kind == "genre", MediaObject.kind.in_(RATED))
                )
                works |= {
                    work
                    for work, tag in tags
                    if str(work) not in granted and genre_of(str(tag)) in restrictions.genres
                }
            season = aliased(MediaObject)
            children: set[UUID] = set()
            if works:
                children = set(
                    await session.scalars(select(MediaObject.id).where(MediaObject.parent_id.in_(works)))
                )
                if children:
                    children |= set(
                        await session.scalars(select(season.id).where(season.parent_id.in_(children)))
                    )
        found = frozenset(works | children)
        if len(self._cache) > 500:
            self._cache.clear()
        self._cache[user] = (time.monotonic(), found)
        return found

    async def hidden(self, viewer: Principal | UUID | None) -> frozenset[UUID]:
        """The titles left out of the lists — those kept from the viewer, unless its master chose to show
        them locked."""
        restrictions = await self.restrictions(viewer)
        if restrictions is None or restrictions.mode == "lock":
            return frozenset()
        return await self.blocked(viewer)

    async def mark(self, viewer: Principal | UUID | None, cards: list[Any]) -> list[Any]:
        """Cards (pydantic models with ``id`` and ``locked``) of titles kept from the viewer, shown locked."""
        blocked = await self.blocked(viewer)
        if not blocked:
            return cards
        return [card.model_copy(update={"locked": True}) if card.id in blocked else card for card in cards]

    def forget(self) -> None:
        self._cache.clear()

    async def check(self, viewer: Principal | UUID | None, object_id: UUID, title: str = "") -> None:
        """Refuse one title the viewer may not open, telling enough for « Ask for access »."""
        if object_id in await self.blocked(viewer):
            rating = await self._rating(object_id)
            restrictions = await self.restrictions(viewer)
            raise Restricted(
                "This title is above this profile's age rating.",
                extensions={
                    "object_id": str(object_id),
                    "name": title,
                    "rating": rating,
                    "can_ask": restrictions is None or restrictions.requests,
                },
            )

    async def _rating(self, object_id: UUID) -> str | None:
        """The strictest age a title (or the series of an episode or a season) is rated for, as « 17+ »."""
        found = await self.rating(object_id)
        return f"{found['age']}+" if found["age"] is not None else None

    async def rating(self, object_id: UUID) -> dict[str, Any]:
        """032: a title's age ratings, source by source (TMDB's countries, the media server), and the
        strictest age they stand for — an episode or a season answers with its series' when it has none."""
        async with self.database.session() as session:
            current: UUID | None = object_id
            for _ in range(3):
                if current is None:
                    break
                row = (
                    await session.execute(
                        select(
                            MediaObject.parent_id,
                            ObjectMetadata.data,
                            MediaObject.effective["content_rating"].astext,
                        )
                        .outerjoin(
                            ObjectMetadata,
                            (ObjectMetadata.object_id == MediaObject.id) & (ObjectMetadata.status == "found"),
                        )
                        .where(MediaObject.id == current)
                    )
                ).one_or_none()
                if row is None:
                    break
                parent, data, server = row
                sources = labelled(data, server)
                if sources:
                    return {
                        "age": strictest_age(v for _, v in sources),
                        "ratings": [{"source": s, "value": v} for s, v in sources],
                    }
                current = parent
        return {"age": None, "ratings": []}

    async def keep(self, viewer: Principal | UUID | None, items: Iterable[Any], key: str = "id") -> list[Any]:
        """The items (objects or mappings) whose ``key`` is a title the viewer's lists may show."""
        blocked = await self.hidden(viewer)
        items = list(items)
        if not blocked:
            return items
        return [item for item in items if _id_of(item, key) not in blocked]

    async def scrub(self, viewer: Principal | UUID | None, payload: Any) -> Any:
        """A response (mappings and lists, as JSON goes) without the entries naming a title kept from the
        viewer — for the many lists of titles a page or a widget draws."""
        blocked = await self.hidden(viewer)
        return _scrub(payload, {str(b) for b in blocked}) if blocked else payload


def _id_of(item: Any, key: str) -> UUID | None:
    raw = item.get(key) if isinstance(item, dict) else getattr(item, key, None)
    if isinstance(raw, UUID):
        return raw
    try:
        return UUID(str(raw)) if raw is not None else None
    except ValueError:
        return None


def _names(item: dict[str, Any], blocked: set[str]) -> bool:
    return any(str(item.get(key)) in blocked for key in IDS if item.get(key) is not None)


def _scrub(payload: Any, blocked: set[str]) -> Any:
    if isinstance(payload, list):
        return [
            _scrub(item, blocked)
            for item in payload
            if not (isinstance(item, dict) and _names(item, blocked))
        ]
    if isinstance(payload, dict):
        return {key: _scrub(value, blocked) for key, value in payload.items()}
    return payload


class GatedWidget:
    """A media widget whose lists leave out what the viewer's age rating keeps from them."""

    def __init__(self, inner: Any, gate: TitleGate) -> None:
        self.inner = inner
        self.gate = gate

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    async def load(self, principal: Principal, config: Any, ctx: Any) -> Any:
        payload = await self.inner.load(principal, config, ctx)
        data = getattr(payload, "data", None)
        if data is None or not await self.gate.hidden(principal):
            return payload
        return replace(payload, data=await self.gate.scrub(principal, dict(data)))


class GatedSearch:
    """The media search provider without the titles the viewer's age rating keeps from them."""

    def __init__(self, inner: Any, gate: TitleGate) -> None:
        self.inner = inner
        self.gate = gate

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    async def _visible(self, principal: Principal, items: Iterable[Any]) -> list[Any]:
        blocked = {str(b) for b in await self.gate.hidden(principal)}
        return [item for item in items if str(getattr(item, "id", "")) not in blocked]

    async def search(
        self, query: Any, principal: Principal, ctx: Any, *, limit: int, cursor: str | None
    ) -> Any:
        result = await self.inner.search(query, principal, ctx, limit=limit, cursor=cursor)
        if not await self.gate.hidden(principal):
            return result
        return replace(result, items=await self._visible(principal, result.items))

    async def suggestions(self, query: Any, principal: Principal, **options: Any) -> Any:
        return await self._visible(principal, await self.inner.suggestions(query, principal, **options))

    async def hydrate(self, ids: Any, principal: Principal) -> Any:
        return await self._visible(principal, await self.inner.hydrate(ids, principal))
