"""Issue 363, #378: the team as a request service — the books, audiobooks, games… no other service asks
for. A member's request is the portal's own (media's: the same « My requests », the same queue, states,
quotas and figures as a film's); this service keeps what was asked, takes the administrators' decision,
and tells the portal once the library has the title (one of its identifiers, else its title by one of its
creators) — through the request service's sync records, as Seerr does."""

import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from uuid import UUID, uuid5

from sqlalchemy import select

from portalab.capabilities.connector_sdk import SourceRecord
from portalab.capabilities.i18n import normalize_for_search
from portalab.capabilities.media import REQUESTS, RequestState, SourceRequest
from portalab.capabilities.media_core import LIBRARY_MATCH, LibraryTitle, WantedTitle
from portalab.capabilities.record_sink import ServiceRef, SinkRegistry
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.errors import NotFound
from portalab.core.logging import get_logger
from portalab.core.time import Clock, utc_now
from portalab.modules.requests.models import OPEN, TitleRequest
from portalab.modules.requests.settings import RequestsConfig

log = get_logger("portalab.requests")
# the team's own « service »: what the portal's requests of books, games… are kept under
TEAM = uuid5(UUID(int=0), "portalab:requests:team")
SOURCE = f"requests:{TEAM}"
_SEPARATORS = re.compile(r"[\W_]+")
SWEEP = 500
# this service's words → the portal's request states
STATES: Mapping[str, RequestState] = {
    "new": "pending",
    "accepted": "approved",
    "in_progress": "processing",
    "available": "available",
    "refused": "declined",
    "cancelled": "cancelled",
}


class RequestNotFound(NotFound):
    default_code = "requests.not_found"
    default_title = "No such request"


def fold(text: str) -> str:
    """Lower case, no accents, every separator a single space."""
    return " ".join(_SEPARATORS.sub(" ", normalize_for_search(text or "")).split())[:300]


def _answer(row: TitleRequest) -> SourceRequest:
    return SourceRequest(external_request_id=str(row.id), state=STATES[row.status], source_state=row.status)


class TeamRequests:
    """``request.service`` for the kinds of titles the administrators open (``requests.config``)."""

    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        config: Any,
        sinks: SinkRegistry,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.config = config  # () -> RequestsConfig
        self.sinks = sinks
        self.clock = clock

    def _now(self) -> datetime:
        return self.clock.now() if self.clock else utc_now()

    def kinds(self) -> list[str]:
        config: RequestsConfig = self.config()
        return list(config.kinds)

    async def submit(
        self, ids: Mapping[str, str], kind: str, title: str, requester: str | None, **options: Any
    ) -> SourceRequest:
        now = self._now()
        year = options.get("year")
        async with self.database.unit_of_work() as uow:
            row = TitleRequest(
                kind=kind[:40],
                title=title.strip()[:300],
                folded=fold(title),
                creators=[str(c)[:120] for c in options.get("creators") or ()][:10],
                year=year if isinstance(year, int) else None,
                details={str(k)[:32]: str(v)[:120] for k, v in dict(options.get("details") or {}).items()},
                ids={str(k)[:32]: [str(v)[:200]] for k, v in ids.items() if v},
                note=str(options.get("note") or "")[:1000] or None,
                status="new",
                created_at=now,
                updated_at=now,
            )
            uow.session.add(row)
            await uow.session.flush()
            return _answer(row)

    async def status(self, external_request_id: str) -> SourceRequest:
        async with self.database.session() as session:
            row = await session.get(TitleRequest, self._id(external_request_id))
        if row is None:
            raise RequestNotFound("No such request.")
        return _answer(row)

    async def decide(self, external_request_id: str, approve: bool) -> SourceRequest:
        """The administrators' decision, taken in the portal's request queue."""
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(TitleRequest, self._id(external_request_id), with_for_update=True)
            if row is None:
                raise RequestNotFound("No such request.")
            if row.status in OPEN:
                row.status, row.updated_at = ("accepted" if approve else "refused"), self._now()
            return _answer(row)

    async def cancel(self, external_request_id: str) -> None:
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(TitleRequest, self._id(external_request_id), with_for_update=True)
            if row is not None and row.status in OPEN:
                row.status, row.updated_at = "cancelled", self._now()

    @staticmethod
    def _id(external_request_id: str) -> UUID:
        try:
            return UUID(external_request_id)
        except ValueError as exc:
            raise RequestNotFound("No such request.") from exc

    async def sweep(self) -> int:
        """The open requests the library now answers: there — told to the portal, which tells the members."""
        async with self.database.session() as session:
            rows = list(
                (
                    await session.execute(
                        select(TitleRequest)
                        .where(TitleRequest.status.in_(OPEN))
                        .order_by(TitleRequest.updated_at)
                        .limit(SWEEP)
                    )
                ).scalars()
            )
        found = await self._in_library(
            [WantedTitle(str(r.id), r.kind, r.title, tuple(r.creators), r.ids) for r in rows]
        )
        if not found:
            return 0
        now = self._now()
        records = []
        async with self.database.unit_of_work() as uow:
            for request_id, there in found.items():
                row = await uow.session.get(TitleRequest, UUID(request_id), with_for_update=True)
                if row is None or row.status not in OPEN:
                    continue
                row.status, row.object_id, row.updated_at = "available", there.object_id, now
                records.append(self._record(row, now))
        await self.tell(records)
        return len(records)

    async def _in_library(self, wanted: Sequence[WantedTitle]) -> Mapping[str, LibraryTitle]:
        providers = self.capabilities.system_providers(LIBRARY_MATCH)
        if not providers or not wanted:
            return {}
        try:
            found: Mapping[str, LibraryTitle] = await providers[0].provider.find(wanted)
            return found
        except Exception as exc:
            log.warning("library lookup failed", extra={"fields": {"error": type(exc).__name__}})
            return {}

    @staticmethod
    def _record(row: TitleRequest, now: datetime) -> SourceRecord:
        return SourceRecord(
            source_system=SOURCE,
            external_id=str(row.id),
            kind=row.kind,
            payload={
                "title": row.title,
                "kind": row.kind,
                "ids": {scheme: values[0] for scheme, values in row.ids.items() if values},
                "state": STATES[row.status],
                "source_state": row.status,
                "object_id": str(row.object_id) if row.object_id else None,
                "available_at": now.isoformat() if row.status == "available" else None,
            },
            observed_at=now,
        )

    async def tell(self, records: Sequence[SourceRecord]) -> None:
        """What changed, told to the portal's requests (the request service's sync records)."""
        sink = self.sinks.get(REQUESTS)
        if sink is None or not records:
            return
        try:
            await sink.upsert(list(records), ServiceRef(service_id=TEAM, source_system=SOURCE))
        except Exception as exc:
            log.warning("requests not told", extra={"fields": {"error": type(exc).__name__}})
