"""#4: asking for a film or a series without leaving the portal.

What one can ask for comes from the request service (``request.discovery``: Seerr, over TMDB) — a search,
shelves like Seerr's own (trending, popular and upcoming films and series) and a title's details (cast,
trailer, seasons and which are there or asked for). Each title is told as the portal knows it too: its
page when the catalog has it, whether it is available, and whether a request is open — mine or someone
else's (never who). Shelves are kept ten minutes per language.
"""

import asyncio
import time
from collections.abc import Sequence
from contextlib import suppress
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.media import REQUEST_DISCOVERY, RequestableDetails, RequestableTitle, unwrap
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.errors import Unavailable
from portalab.modules.media.identity.resolver import MediaNotFound
from portalab.modules.media.models import ExternalId, MediaObject, MediaRequest
from portalab.modules.media.observability import log
from portalab.modules.media.requests.service_quota import kind_of

SHELF_TTL = 600.0
TIMEOUT = 12.0
SHELVES = ("trending", "popular_movies", "popular_series", "upcoming_movies", "upcoming_series")
OPEN = ("pending", "approved", "processing")


class DiscoveryUnavailable(Unavailable):
    default_code = "media.discovery_unavailable"
    default_title = "The request service cannot be searched right now"


class RequestableCatalog:
    def __init__(self, database: Database, capabilities: CapabilityRegistry) -> None:
        self.database = database
        self.capabilities = capabilities
        self._shelves: dict[tuple[str, str], tuple[float, list[RequestableTitle]]] = {}

    def provider(self) -> Any | None:
        with suppress(Exception):
            providers = self.capabilities.system_providers(REQUEST_DISCOVERY)
            if providers:
                return providers[0].provider
        return None

    def configured(self) -> bool:
        return self.provider() is not None

    async def _ask(self, call: Any) -> Any:
        try:
            return unwrap(await asyncio.wait_for(call, timeout=TIMEOUT))
        except Exception as exc:
            log.info("request discovery unavailable", extra={"reason": type(exc).__name__})
            raise DiscoveryUnavailable("The request service did not answer.") from exc

    # --- titles ---------------------------------------------------------------------------------------
    async def search(self, query: str, user: UUID, language: str, page: int = 1) -> list[dict[str, Any]]:
        provider = self.provider()
        if provider is None or not query.strip():
            return []
        titles = await self._ask(provider.search(query, language, page))
        return await self.annotate(list(titles), user)

    async def shelf(self, name: str, user: UUID, language: str) -> list[dict[str, Any]]:
        provider = self.provider()
        if provider is None or name not in SHELVES:
            return []
        cached = self._shelves.get((name, language))
        if cached and time.monotonic() - cached[0] < SHELF_TTL:
            titles = cached[1]
        else:
            titles = list(await self._ask(provider.shelf(name, language)))
            self._shelves[(name, language)] = (time.monotonic(), titles)
        return await self.annotate(titles, user)

    async def details(self, kind: str, tmdb_id: str, user: UUID, language: str) -> dict[str, Any]:
        provider = self.provider()
        if provider is None:
            raise DiscoveryUnavailable("No request service is connected.")
        found: RequestableDetails | None = await self._ask(provider.details(kind, tmdb_id, language))
        if found is None:
            raise MediaNotFound("This title does not exist.")
        [card] = await self.annotate([found.title], user)
        return {
            **card,
            "genres": list(found.genres),
            "runtime": found.runtime,
            "tagline": found.tagline,
            "cast": [{"name": n, "character": c, "profile": p} for n, c, p in found.cast],
            "trailer": found.trailer,
            "ids": dict(found.ids),
            "four_k": found.four_k,
            "metadata": dict(found.metadata),
            "seasons": [
                {
                    "number": s.number,
                    "name": s.name,
                    "episodes": s.episodes,
                    "air_date": s.air_date,
                    "status": s.status,
                }
                for s in found.seasons
            ],
        }

    # --- as the portal knows them ---------------------------------------------------------------------
    async def annotate(self, titles: Sequence[RequestableTitle], user: UUID) -> list[dict[str, Any]]:
        """Each title with its page in the catalog (when there), whether it is available, and the open
        request for it (mine, or someone else's — never who)."""
        if not titles:
            return []
        wanted = {t.tmdb_id for t in titles}
        async with self.database.session() as session:
            known: dict[tuple[str, str], tuple[UUID, bool]] = {}
            rows = await session.execute(
                select(ExternalId.value, MediaObject.kind, MediaObject.id, MediaObject.available)
                .join(MediaObject, MediaObject.id == ExternalId.object_id)
                .where(
                    ExternalId.scheme == "tmdb",
                    ExternalId.value.in_(wanted),
                    MediaObject.kind.in_(("movie", "series")),
                    MediaObject.status == "active",
                )
            )
            for value, kind, object_id, available in rows:
                current = known.get((value, kind))
                if current is None or (available and not current[1]):
                    known[(value, kind)] = (object_id, bool(available))
            asked: dict[tuple[str, str], bool] = {}  # (tmdb, movie|tv) → mine
            requests = await session.execute(
                select(MediaRequest.external_ref, MediaRequest.requester_user_id).where(
                    MediaRequest.state.in_(OPEN)
                )
            )
            for ref, requester in requests:
                tmdb = str(((ref or {}).get("ids") or {}).get("tmdb") or "")
                if tmdb in wanted:
                    key = (tmdb, kind_of(str((ref or {}).get("kind") or "")))
                    asked[key] = asked.get(key, False) or requester == user
        out = []
        for title in titles:
            object_id, available = known.get((title.tmdb_id, title.kind), (None, False))
            request_key = (title.tmdb_id, kind_of(title.kind))
            status = "available" if available else title.status
            out.append(
                {
                    "tmdb_id": title.tmdb_id,
                    "kind": title.kind,
                    "title": title.title,
                    "year": title.year,
                    "overview": title.overview,
                    "poster": title.poster,
                    "backdrop": title.backdrop,
                    "rating": title.rating,
                    "release_date": title.release_date,
                    "status": status,
                    "object_id": str(object_id) if object_id else None,
                    "request": {"mine": asked[request_key]} if request_key in asked else None,
                    "route": f"/media/discover/{title.kind}/{title.tmdb_id}",
                }
            )
        return out
