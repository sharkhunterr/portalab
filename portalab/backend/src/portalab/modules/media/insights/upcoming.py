"""Upcoming releases (027): what Radarr and Sonarr announce for the coming weeks — films in cinemas, on
digital or physical release, new episodes — merged across services, tied to the catalog when possible (for
the poster and the detail page), and cached a few minutes (calendars change slowly)."""

import asyncio
import time
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.media import CALENDAR, SourceRelease, unwrap
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.media.common import strong_ids
from portalab.modules.media.models import ExternalId, MediaObject

TTL = 600
TIMEOUT = 15
MAX_DAYS = 120


class Upcoming:
    def __init__(self, database: Database, capabilities: CapabilityRegistry, *, clock: Clock | None = None):
        self.database = database
        self.capabilities = capabilities
        self.clock = clock
        self._cache: tuple[float, int, list[dict[str, Any]]] | None = None

    def providers(self) -> list[Any]:
        try:
            return [r.provider for r in self.capabilities.system_providers(CALENDAR)]
        except Exception:
            return []

    async def _object(self, release: SourceRelease) -> UUID | None:
        async with self.database.session() as session:
            for scheme, value in strong_ids(release.ids).items():
                found = await session.scalar(
                    select(ExternalId.object_id)
                    .join(MediaObject, MediaObject.id == ExternalId.object_id)
                    .where(
                        ExternalId.scheme == scheme, ExternalId.value == value, MediaObject.status == "active"
                    )
                )
                if found is not None:
                    return found
        return None

    async def list(self, days: int = 30) -> list[dict[str, Any]]:
        days = max(1, min(days, MAX_DAYS))
        if self._cache and self._cache[1] >= days and time.monotonic() - self._cache[0] < TTL:
            limit = utc_now(self.clock) + timedelta(days=days)
            return [r for r in self._cache[2] if r["at"] <= limit.isoformat()]
        start = utc_now(self.clock) - timedelta(days=1)
        end = start + timedelta(days=days + 1)
        releases: list[SourceRelease] = []
        results = await asyncio.gather(
            *(asyncio.wait_for(p.upcoming(start, end), timeout=TIMEOUT) for p in self.providers()),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, BaseException):
                continue
            try:
                releases.extend(unwrap(result))
            except Exception:  # noqa: S112 — an unavailable calendar is skipped
                continue
        seen: set[tuple[str, str, str]] = set()
        out: list[dict[str, Any]] = []
        for release in sorted(releases, key=lambda r: r.release_at):
            if not start <= release.release_at <= end:  # a calendar may answer beyond the window
                continue
            key = (
                release.kind,
                release.parent_title or release.title,
                release.release_type + release.release_at.date().isoformat(),
            )
            if key in seen:
                continue
            seen.add(key)
            object_id = await self._object(release)
            out.append(
                {
                    "kind": release.kind,
                    "title": release.title,
                    "parent_title": release.parent_title,
                    "season": release.season,
                    "episode": release.episode,
                    "at": release.release_at.isoformat(),
                    "type": release.release_type,
                    "available": release.available,
                    "object_id": str(object_id) if object_id else None,
                    "overview": release.overview,
                    "ids": dict(release.ids),
                }
            )
        self._cache = (time.monotonic(), days, out)
        return out
