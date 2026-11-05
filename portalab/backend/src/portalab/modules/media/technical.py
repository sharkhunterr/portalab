"""#354: a title's technical sheet, for the team answering a member's report on it — each media server's side
(when it was added, its files: path, size, container, length, bitrate, and their streams: the video's codec,
resolution and dynamic range, the audio tracks' language, codec and channels, the subtitles) and its download
manager's (the release grabbed, from which indexer, by which client, the torrent's hash, the quality and
size). Asked of the services when the team looks — nothing stored; a service that does not answer is left
out."""

import asyncio
from collections.abc import Mapping
from dataclasses import asdict
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.health import SERVICE_DIRECTORY
from portalab.capabilities.media import TECHNICAL, SourceAcquisition, TechnicalSheet, unwrap
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.logging import get_logger
from portalab.modules.media.models import SourceItem
from portalab.modules.media.requests.journey import RequestJourney

log = get_logger("portalab.media.technical")
TIMEOUT_S = 10


def _iso(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _server(name: str, sheet: TechnicalSheet) -> dict[str, Any]:
    return {
        "service": name,
        "added_at": _iso(sheet.added_at),
        "files": [
            {
                **{k: v for k, v in asdict(f).items() if k != "streams"},
                "streams": [asdict(s) for s in f.streams],
            }
            for f in sheet.files
        ],
    }


def _acquisition(found: SourceAcquisition) -> dict[str, Any]:
    return {
        "service": found.service_name,
        "added_at": _iso(found.added_at),
        "quality": found.quality,
        "size": found.size,
        "files": found.files,
        "expected": found.expected,
        "link": found.link,
        "events": [
            {
                "event": e.event,
                "at": _iso(e.at),
                "release": e.release,
                "indexer": e.indexer,
                "client": e.client,
                "download_id": e.download_id,
            }
            for e in found.history
            if e.event in ("grabbed", "imported", "failed", "deleted")
        ],
    }


class MediaTechnicalSheets:
    def __init__(self, database: Database, capabilities: CapabilityRegistry, journey: RequestJourney) -> None:
        self.database = database
        self.capabilities = capabilities
        self.journey = journey

    async def _name(self, service_id: UUID) -> str:
        providers = self.capabilities.system_providers(SERVICE_DIRECTORY)
        try:
            info = await providers[0].provider.service(str(service_id)) if providers else None
        except Exception:
            info = None
        return str(getattr(info, "name", None) or service_id)

    async def _one(self, provider: Any, item: SourceItem) -> dict[str, Any] | None:
        try:
            sheet = unwrap(await asyncio.wait_for(provider.technical(item.external_id, item.kind), TIMEOUT_S))
        except Exception as error:
            log.info("technical sheet unavailable", extra={"reason": type(error).__name__})
            return None
        return (
            _server(await self._name(item.service_id), sheet) if isinstance(sheet, TechnicalSheet) else None
        )

    async def sheet(self, viewer: Principal, object_id: UUID) -> Mapping[str, Any]:
        async with self.database.session() as session:
            items = list(
                (
                    await session.execute(
                        select(SourceItem).where(
                            SourceItem.object_id == object_id, SourceItem.active.is_(True)
                        )
                    )
                ).scalars()
            )
        providers = {p.instance_ref: p.provider for p in self.capabilities.system_providers(TECHNICAL)}
        asked = [(providers[str(i.service_id)], i) for i in items if str(i.service_id) in providers]
        servers = [s for s in await asyncio.gather(*(self._one(p, i) for p, i in asked)) if s is not None]
        try:
            found = await self.journey.acquisition_of(viewer, object_id)
        except Exception as error:
            log.info("acquisition unavailable", extra={"reason": type(error).__name__})
            found = None
        return {"servers": servers, "acquisition": _acquisition(found) if found is not None else None}
