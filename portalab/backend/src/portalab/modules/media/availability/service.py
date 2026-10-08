"""``AvailabilityService`` (T017; R10, FR-033..035): three independent facts, side by side, never collapsed
into one flag — the object's **availability** (does an active source hold it), each source's **service
health** (006 ``health.service_state``) and its **sync state** (005 directory: last success/attempt and
error class). A service outage or a failed sync changes none of the catalog facts; stale data is marked
with its ``as_of``."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.health import SERVICE_DIRECTORY, SERVICE_STATE
from portalab.capabilities.media import ITEM_LINKS, unwrap
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.media.models import MediaObject, SourceItem


@dataclass(frozen=True, slots=True)
class SourceStatus:
    service_id: str
    service_name: str | None
    connector: str | None
    present: bool  # the source still lists the item (active)
    availability: str  # available | unavailable | unknown (as reported by the source)
    observed_at: datetime
    last_seen_at: datetime
    service_state: str  # 006: operational | degraded | unavailable | maintenance | unknown
    service_state_as_of: datetime | None
    sync_status: str  # 005: idle | running | failed | … (unknown without a directory)
    last_sync_success_at: datetime | None
    last_sync_error: str | None
    last_sync_attempt_at: datetime | None = None  # 027: an error only counts when no success came after
    link: str | None = None
    item_link: str | None = None  # 027: this title's page in the service, at its public address
    variant: str | None = None  # 027: which copy this is in the service (a game's platform, region…)


class AvailabilityService:
    def __init__(self, database: Database, capabilities: CapabilityRegistry, *, clock: Clock | None = None):
        self.database = database
        self.capabilities = capabilities
        self.clock = clock

    def _port(self, name: str) -> Any | None:
        try:
            providers = self.capabilities.system_providers(name)
        except Exception:
            return None
        return providers[0].provider if providers else None

    async def _item_link(self, item: SourceItem, base: str | None) -> str | None:
        """027: the service's public address joined to the title's own page in it (Jellyfin, Grimmory…), or
        the service's universal address for it (Plex)."""
        try:
            providers = self.capabilities.system_providers(ITEM_LINKS)
        except Exception:
            return None
        provider = next((p.provider for p in providers if p.instance_ref == str(item.service_id)), None)
        if provider is None:
            return None
        try:
            path = unwrap(await asyncio.wait_for(provider.item_path(item.external_id, item.kind), timeout=5))
        except Exception:
            return None
        if isinstance(path, str) and path.startswith("https://"):
            return path
        if not base or not isinstance(path, str) or not path.startswith("/"):
            return None
        return f"{base.rstrip('/')}{path}"

    async def sources(self, object_id: UUID) -> tuple[bool, list[SourceStatus], datetime]:
        async with self.database.session() as session:
            row = await session.get(MediaObject, object_id)
            items = (
                (
                    await session.execute(
                        select(SourceItem)
                        .where(SourceItem.object_id == object_id)
                        .order_by(SourceItem.active.desc(), SourceItem.source_system)
                    )
                )
                .scalars()
                .all()
            )
        directory, states = self._port(SERVICE_DIRECTORY), self._port(SERVICE_STATE)
        out: list[SourceStatus] = []
        for item in items:
            info = state = None
            try:
                info = await directory.service(str(item.service_id)) if directory is not None else None
            except Exception:
                info = None
            try:
                state = await states.get(str(item.service_id)) if states is not None else None
            except Exception:
                state = None
            out.append(
                SourceStatus(
                    service_id=str(item.service_id),
                    service_name=getattr(info, "name", None),
                    connector=getattr(info, "connector", None),
                    present=item.active,
                    availability=item.availability if item.active else "unavailable",
                    observed_at=item.observed_at,
                    last_seen_at=item.last_seen_at,
                    service_state=getattr(state, "state", "unknown"),
                    service_state_as_of=getattr(state, "as_of", None),
                    sync_status=getattr(info, "sync_status", "unknown"),
                    last_sync_success_at=getattr(info, "last_sync_success_at", None),
                    last_sync_error=getattr(info, "last_sync_error", None),
                    last_sync_attempt_at=getattr(info, "last_sync_attempt_at", None),
                    link=getattr(info, "link", None),
                    item_link=await self._item_link(item, getattr(info, "link", None)),
                    variant=str((item.payload or {}).get("variant") or "")[:200] or None,
                )
            )
        as_of = max((s.last_seen_at for s in out), default=utc_now(self.clock))
        return (bool(row.available) if row is not None else False), out, as_of
