"""Search events (T034; R9, FR-030): ``search.performed`` carries **counts only** (per kind, timing, mode) —
never the query text — deduplicated on the request id; ``search.provider_failed`` is a diagnostic,
deduplicated per kind and minute."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from portalab.capabilities.events import EventType, EventTypeRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.modules.search.observability import log

OWNER = "module:search"


class SearchPerformed(BaseModel):
    request_id: str = Field(max_length=64)
    result_counts: dict[str, int]
    took_ms: int
    mode: Literal["exact", "semantic", "mixed"]
    semantic: Literal["ok", "unavailable", "off"]


class ProviderFailed(BaseModel):
    kind: str = Field(max_length=96)
    reason: Literal["timeout", "error"]
    minute: str


def register_event_types(registry: EventTypeRegistry) -> None:
    for name, schema, dedup, visibility in (
        ("search.performed", SearchPerformed, ("request_id",), "private"),
        ("search.provider_failed", ProviderFailed, ("kind", "reason", "minute"), "restricted"),
    ):
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=schema,
                    open_payload=False,
                    dedup_fields=dedup,
                    retention_class="technical",
                    visibility_class=visibility,  # type: ignore[arg-type]
                    automatable=name == "search.performed",
                )
            )


class SearchEvents:
    def __init__(self, database: Database, events: EventPublisher) -> None:
        self.database = database
        self.events = events

    async def performed(
        self,
        principal: Principal,
        request_id: str,
        counts: dict[str, int],
        took_ms: int,
        mode: str,
        semantic: str,
        at: datetime,
    ) -> None:
        try:
            async with self.database.unit_of_work() as uow:
                await self.events.publish(
                    uow.session,
                    "search.performed",
                    {
                        "request_id": request_id,
                        "result_counts": counts,
                        "took_ms": took_ms,
                        "mode": mode,
                        "semantic": semantic,
                    },
                    occurred_at=at,
                    actor=principal,
                    source="search",
                )
        except Exception:
            log.warning("search.performed not recorded")  # usage statistics never break search

    async def provider_failed(self, kind: str, reason: str, at: datetime) -> None:
        try:
            async with self.database.unit_of_work() as uow:
                await self.events.publish(
                    uow.session,
                    "search.provider_failed",
                    {"kind": kind, "reason": reason, "minute": at.strftime("%Y-%m-%dT%H:%M")},
                    occurred_at=at,
                    source="search",
                )
        except Exception:
            log.warning("search.provider_failed not recorded")
