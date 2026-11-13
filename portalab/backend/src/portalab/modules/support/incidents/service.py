"""``IncidentService`` (T010, T011; US3): the one incident system of the portal.

* lifecycle ``investigating → identified → monitoring → resolved`` recorded in an **append-only** timeline
  (each update carries state, severity and a public message); resolving never depends on any ticket;
* idempotent creation per ``(source, dedup_key)`` — a repeated escalation (025) or health signal (006)
  returns the existing incident and only adds services/evidence;
* evidence is kept as opaque pointers (``observability:anomaly:<id>``), never payloads;
* every staff change is audited (severity changes and critical resolutions are sensitive) and published
  as ``incident.created|updated|resolved`` (dedup ``(incident_id, update_seq)``).
"""

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.support import STATES, normalize_severity
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound, ValidationFailed
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock, utc_now
from portalab.modules.support.models import Incident, IncidentEvidence, IncidentServiceLink, IncidentUpdate

OPEN_STATES: tuple[str, ...] = ("investigating", "identified", "monitoring")
SOURCES: tuple[str, ...] = ("manual", "observability", "health", "automation")


class IncidentNotFound(NotFound):
    default_code = "incident.not_found"
    default_title = "Incident not found"


class IncidentResolved(Conflict):
    default_code = "incident.resolved"
    default_title = "This incident is resolved"


class IncidentVersionConflict(Conflict):
    default_code = "incident.version_conflict"
    default_title = "The incident changed meanwhile"


class InvalidIncident(ValidationFailed):
    default_code = "incident.invalid"
    default_title = "Invalid incident"


@dataclass
class IncidentView:
    id: UUID
    number: int
    title: str
    summary: str
    severity: str
    state: str
    source: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    version: int
    service_ids: list[str] = field(default_factory=list)
    updates: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    banner: bool = False

    @property
    def reference(self) -> str:
        return f"INC-{self.number:04d}"


@dataclass(frozen=True, slots=True)
class Change:
    """Notification hook input: what happened to which incident (ids only)."""

    kind: str  # created | updated | resolved
    incident_id: UUID
    number: int
    title: str
    severity: str
    service_ids: tuple[str, ...]
    # issue 398: what the notification tells beyond the title — where it stands, what was said, since when
    summary: str = ""
    state: str = ""
    message: str = ""
    created_at: datetime | None = None
    resolved_at: datetime | None = None
    version: int = 0

    @classmethod
    def of(cls, kind: str, view: "IncidentView", message: str = "") -> "Change":
        return cls(
            kind, view.id, view.number, view.title, view.severity, tuple(view.service_ids),
            summary=view.summary, state=view.state, message=message, created_at=view.created_at,
            resolved_at=view.resolved_at, version=view.version,
        )  # fmt: skip


def evidence_ref(evidence: Mapping[str, Any]) -> str:
    """An opaque pointer for an evidence mapping — never the payload itself."""
    explicit = evidence.get("evidence_ref")
    if isinstance(explicit, str) and explicit:
        return explicit[:200]
    anomaly = evidence.get("anomaly_id")
    if anomaly:
        return f"observability:anomaly:{anomaly}"[:200]
    digest = hashlib.sha256(json.dumps(evidence, sort_keys=True, default=str).encode()).hexdigest()[:32]
    return f"evidence:{digest}"


class IncidentService:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        *,
        clock: Clock | None = None,
        on_change: Callable[[Change], Any] | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.audit = audit
        self.clock = clock
        self.on_change = on_change

    # --- reading -------------------------------------------------------------------------------------
    async def _view(self, session: AsyncSession, row: Incident, *, timeline: bool = True) -> IncidentView:
        services = list(
            (
                await session.execute(
                    select(IncidentServiceLink.service_id)
                    .where(IncidentServiceLink.incident_id == row.id)
                    .order_by(IncidentServiceLink.service_id)
                )
            ).scalars()
        )
        view = IncidentView(
            row.id,
            row.number,
            row.title,
            row.summary,
            row.severity,
            row.state,
            row.source,
            row.created_at,
            row.updated_at,
            row.resolved_at,
            row.version,
            services,
            banner=row.banner,
        )
        if timeline:
            updates = (
                await session.execute(
                    select(IncidentUpdate)
                    .where(IncidentUpdate.incident_id == row.id)
                    .order_by(IncidentUpdate.update_seq)
                )
            ).scalars()
            view.updates = [
                {
                    "seq": u.update_seq,
                    "state": u.state,
                    "severity": u.severity,
                    "message": u.message,
                    "at": u.created_at.isoformat(),
                    "author_user_id": str(u.author_user_id) if u.author_user_id else None,
                }
                for u in updates
            ]
            view.evidence = list(
                (
                    await session.execute(
                        select(IncidentEvidence.evidence_ref)
                        .where(IncidentEvidence.incident_id == row.id)
                        .order_by(IncidentEvidence.added_at)
                    )
                ).scalars()
            )
        return view

    async def get(self, incident_id: UUID) -> IncidentView:
        async with self.database.session() as session:
            row = await session.get(Incident, incident_id)
            if row is None:
                raise IncidentNotFound("This incident does not exist.")
            return await self._view(session, row)

    async def list(
        self, *, state: str | None = None, service_id: str | None = None, limit: int = 100
    ) -> list[IncidentView]:
        stmt = select(Incident).order_by(Incident.created_at.desc(), Incident.number.desc()).limit(limit)
        if state == "open":
            stmt = stmt.where(Incident.state.in_(OPEN_STATES))
        elif state is not None:
            stmt = stmt.where(Incident.state == state)
        if service_id is not None:
            stmt = stmt.where(
                Incident.id.in_(
                    select(IncidentServiceLink.incident_id).where(
                        IncidentServiceLink.service_id == service_id
                    )
                )
            )
        async with self.database.session() as session:
            rows = (await session.execute(stmt)).scalars().all()
            return [await self._view(session, row, timeline=False) for row in rows]

    # --- writing -------------------------------------------------------------------------------------
    async def create(
        self,
        actor: Principal | None,
        *,
        title: str,
        severity: str,
        source: str = "manual",
        service_ids: Iterable[str] = (),
        summary: str = "",
        dedup_key: str | None = None,
        evidence: Iterable[str] = (),
        message: str | None = None,
        banner: bool = False,
    ) -> tuple[IncidentView, bool]:
        """``(incident, created)`` — ``created`` is false when ``(source, dedup_key)`` already exists."""
        title = " ".join(title.split())[:200]
        if not title:
            raise InvalidIncident("An incident needs a title.")
        if source not in SOURCES:
            raise InvalidIncident(f"Unknown source {source!r}.")
        try:
            severity = normalize_severity(severity)
        except ValueError as exc:
            raise InvalidIncident(str(exc)) from exc
        services = sorted({str(s)[:64] for s in service_ids if str(s).strip()})
        refs = [r[:200] for r in evidence if r]
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            if dedup_key is not None:
                existing = (
                    await session.execute(
                        select(Incident)
                        .where(Incident.source == source, Incident.dedup_key == dedup_key)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    await self._add_services(session, existing.id, services)
                    await self._add_evidence(session, existing.id, refs, now)
                    return await self._view(session, existing), False
            number = int(await session.scalar(text("SELECT nextval('support.incident_number_seq')")) or 0)
            row = Incident(
                number=number,
                title=title,
                summary=summary.strip()[:4000],
                severity=severity,
                state="investigating",
                source=source,
                dedup_key=dedup_key,
                created_by=(actor.acting_for or actor.user_id) if actor else None,
                created_at=now,
                updated_at=now,
                version=1,
                banner=banner,
            )
            session.add(row)
            await session.flush()
            await self._add_services(session, row.id, services)
            await self._add_evidence(session, row.id, refs, now)
            await self._append(session, row, actor, message or summary or title, now)
            await self._publish(session, "incident.created", row, 1, actor, now)
            if actor is not None:
                await self._audit(
                    session, actor, "incident.created", row, {"severity": severity}, severity == "critical"
                )
            view = await self._view(session, row)
        self._notify(Change.of("created", view))
        return view, True

    async def update(
        self,
        actor: Principal,
        incident_id: UUID,
        *,
        message: str,
        state: str | None = None,
        if_match: int | None = None,
    ) -> IncidentView:
        message = message.strip()
        if not message:
            raise InvalidIncident("An update needs a message.")
        if state is not None and (state not in STATES or state == "resolved"):
            raise InvalidIncident(
                "Use resolve to close an incident; other states: investigating, identified, monitoring."
            )
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            row = await self._locked(session, incident_id, if_match)
            if row.state == "resolved":
                raise IncidentResolved("This incident is resolved; open a new one.")
            if state is not None:
                row.state = state
            seq = await self._append(session, row, actor, message[:4000], now)
            row.updated_at, row.version = now, row.version + 1
            await self._publish(session, "incident.updated", row, seq, actor, now)
            await self._audit(session, actor, "incident.updated", row, {"state": row.state}, False)
            view = await self._view(session, row)
        self._notify(Change.of("updated", view, message))
        return view

    async def patch(
        self,
        actor: Principal,
        incident_id: UUID,
        *,
        severity: str | None = None,
        service_ids: Sequence[str] | None = None,
        title: str | None = None,
        summary: str | None = None,
        banner: bool | None = None,
        if_match: int | None = None,
    ) -> IncidentView:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            row = await self._locked(session, incident_id, if_match)
            changed: dict[str, Any] = {}
            if severity is not None:
                try:
                    severity = normalize_severity(severity)
                except ValueError as exc:
                    raise InvalidIncident(str(exc)) from exc
                if severity != row.severity:
                    changed["severity"] = {"from": row.severity, "to": severity}
                    row.severity = severity
            if title is not None and title.strip():
                row.title = " ".join(title.split())[:200]
                changed["title"] = True
            if summary is not None:
                row.summary = summary.strip()[:4000]
                changed["summary"] = True
            if banner is not None and banner != row.banner:
                row.banner = banner
                changed["banner"] = banner
            if service_ids is not None:
                wanted = sorted({str(s)[:64] for s in service_ids if str(s).strip()})
                await session.execute(
                    delete(IncidentServiceLink).where(IncidentServiceLink.incident_id == row.id)
                )
                await self._add_services(session, row.id, wanted)
                changed["services"] = len(wanted)
            if not changed:
                return await self._view(session, row)
            seq = None
            if "severity" in changed:
                seq = await self._append(session, row, actor, f"Severity changed to {row.severity}.", now)
            row.updated_at, row.version = now, row.version + 1
            await self._publish(
                session,
                "incident.updated",
                row,
                seq or await self._last_seq(session, row.id),
                actor,
                now,
                revision=row.version,
            )
            sensitive = "severity" in changed and "critical" in (
                changed["severity"]["from"],
                changed["severity"]["to"],
            )
            await self._audit(
                session, actor, "incident.changed", row, changed, sensitive or "severity" in changed
            )
            view = await self._view(session, row)
        self._notify(Change.of("updated", view))
        return view

    async def resolve(
        self, actor: Principal | None, incident_id: UUID, *, message: str, if_match: int | None = None
    ) -> IncidentView:
        """``actor`` ``None``: the portal itself closes it (027: a service that came back)."""
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            session = uow.session
            row = await self._locked(session, incident_id, if_match)
            if row.state == "resolved":
                return await self._view(session, row)
            row.state, row.resolved_at = "resolved", now
            seq = await self._append(session, row, actor, message.strip()[:4000] or "Resolved.", now)
            row.updated_at, row.version = now, row.version + 1
            await self._publish(session, "incident.resolved", row, seq, actor, now)
            if actor is not None:
                await self._audit(
                    session,
                    actor,
                    "incident.resolved",
                    row,
                    {"severity": row.severity},
                    row.severity == "critical",
                )
            view = await self._view(session, row)
        self._notify(Change.of("resolved", view, message))
        return view

    async def attach(self, incident_id: UUID, refs: Iterable[str]) -> IncidentView | None:
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(Incident, incident_id, with_for_update=True)
            if row is None or row.state == "resolved":
                return None
            await self._add_evidence(uow.session, row.id, list(refs), utc_now(self.clock))
            return await self._view(uow.session, row)

    async def link(self, incident_id: UUID, service_id: str) -> bool:
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(Incident, incident_id)
            if row is None:
                return False
            await self._add_services(uow.session, row.id, [service_id[:64]])
            return True

    # --- internals -----------------------------------------------------------------------------------
    async def _locked(self, session: AsyncSession, incident_id: UUID, if_match: int | None) -> Incident:
        row = await session.get(Incident, incident_id, with_for_update=True)
        if row is None:
            raise IncidentNotFound("This incident does not exist.")
        if if_match is not None and if_match != row.version:
            raise IncidentVersionConflict(
                "The incident changed meanwhile; reload it.", extensions={"version": row.version}
            )
        return row

    async def _last_seq(self, session: AsyncSession, incident_id: UUID) -> int:
        return int(
            await session.scalar(
                select(func.coalesce(func.max(IncidentUpdate.update_seq), 0)).where(
                    IncidentUpdate.incident_id == incident_id
                )
            )
            or 0
        )

    async def _append(
        self, session: AsyncSession, row: Incident, actor: Principal | None, message: str, now: datetime
    ) -> int:
        seq = await self._last_seq(session, row.id) + 1
        session.add(
            IncidentUpdate(
                incident_id=row.id,
                update_seq=seq,
                state=row.state,
                severity=row.severity,
                message=message,
                author_user_id=(actor.acting_for or actor.user_id) if actor else None,
                created_at=now,
            )
        )
        await session.flush()
        return seq

    async def _add_services(self, session: AsyncSession, incident_id: UUID, services: Iterable[str]) -> None:
        for service_id in services:
            await session.execute(
                insert(IncidentServiceLink)
                .values(incident_id=incident_id, service_id=service_id)
                .on_conflict_do_nothing()
            )

    async def _add_evidence(
        self, session: AsyncSession, incident_id: UUID, refs: Iterable[str], now: datetime
    ) -> None:
        for ref in refs:
            await session.execute(
                insert(IncidentEvidence)
                .values(incident_id=incident_id, evidence_ref=ref[:200], added_at=now)
                .on_conflict_do_nothing()
            )

    async def _publish(
        self,
        session: AsyncSession,
        event_type: str,
        row: Incident,
        seq: int,
        actor: Principal | None,
        now: datetime,
        *,
        revision: int | None = None,
    ) -> None:
        payload = {
            "incident_id": str(row.id),
            "update_seq": seq,
            "state": row.state,
            "severity": row.severity,
            "revision": revision or row.version,
        }
        await self.events.publish(
            session,
            event_type,
            payload,
            occurred_at=now,
            actor=actor,
            source="support",
            dedup_key=f"{event_type}:{row.id}:{seq}:{revision or row.version}",
        )

    async def _audit(
        self,
        session: AsyncSession,
        actor: Principal,
        action: str,
        row: Incident,
        context: Mapping[str, Any],
        sensitive: bool,
    ) -> None:
        await self.audit.record(
            session,
            AuditRecord(
                action=action,
                actor=actor,
                resource=ResourceRef("incident", str(row.id)),
                decision="allow",
                result="success",
                context=dict(context),
                sensitive=sensitive,
            ),
        )

    def _notify(self, change: Change) -> None:
        if self.on_change is not None:
            self.on_change(change)
