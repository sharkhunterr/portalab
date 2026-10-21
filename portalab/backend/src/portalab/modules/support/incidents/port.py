"""``support.incidents`` port implementation (T010): what Health (006), Observability (025) and automations
call. System principal; idempotent ``create`` per ``(source, dedup_key)`` (025 escalations default to the
anomaly id); ``attach`` returns ``None`` for a resolved incident so the caller opens a new one."""

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from portalab.capabilities.health import IncidentRef
from portalab.modules.support.incidents.service import (
    SOURCES,
    IncidentNotFound,
    IncidentService,
    IncidentView,
    evidence_ref,
)


def _ref(view: IncidentView) -> IncidentRef:
    return IncidentRef(
        id=str(view.id),
        title=view.title,
        status=view.state,
        opened_at=view.created_at,
        extra={"number": view.reference, "severity": view.severity, "service_ids": list(view.service_ids)},
    )


def _uuid(value: str) -> UUID | None:
    try:
        return UUID(str(value))
    except ValueError:
        return None


class IncidentsPort:
    def __init__(self, service: IncidentService) -> None:
        self.service = service

    async def create(
        self,
        *,
        title: str,
        source: str,
        severity: str,
        evidence: Mapping[str, Any],
        service_ids: Sequence[str] = (),
        dedup_key: str | None = None,
        summary: str | None = None,
        banner: bool = False,
    ) -> IncidentRef:
        source = source if source in SOURCES else "automation"
        if dedup_key is None and evidence.get("anomaly_id"):
            dedup_key = f"anomaly:{evidence['anomaly_id']}"
        services = list(service_ids) or ([str(evidence["service_id"])] if evidence.get("service_id") else [])
        view, _ = await self.service.create(
            None,
            title=title,
            severity=severity,
            source=source,
            service_ids=services,
            summary=summary or "",
            dedup_key=dedup_key,
            evidence=[evidence_ref(evidence)] if evidence else [],
            banner=banner,
        )
        return _ref(view)

    async def attach(self, incident_id: str, evidence: Mapping[str, Any]) -> IncidentRef | None:
        key = _uuid(incident_id)
        if key is None:
            return None
        view = await self.service.attach(key, [evidence_ref(evidence)])
        return _ref(view) if view is not None else None

    async def link(self, service_id: str, incident_id: str) -> None:
        key = _uuid(incident_id)
        if key is not None:
            await self.service.link(key, service_id)

    async def resolve_for_service(self, service_id: str, *, source: str, message: str) -> int:
        """027: close the open incidents a source declared for a service (a service that came back) —
        never the ones a person opened."""
        closed = 0
        for view in await self.service.list(state="open", service_id=service_id):
            if view.source == source:
                await self.service.resolve(None, view.id, message=message)
                closed += 1
        return closed

    async def open_for_service(self, service_id: str) -> list[IncidentRef]:
        return [_ref(view) for view in await self.service.list(state="open", service_id=service_id)]

    async def get(self, incident_id: str) -> IncidentRef | None:
        key = _uuid(incident_id)
        if key is None:
            return None
        try:
            return _ref(await self.service.get(key))
        except IncidentNotFound:
            return None
