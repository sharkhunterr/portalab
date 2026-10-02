"""Observation → Anomaly → Incident (T024; R5, FR-018/019, CD-020).

A finding becomes (or refreshes) one **anomaly** per fingerprint. The escalation policy decides: at or
above ``escalation.autoSeverity`` and without ``escalation.requireValidation`` it escalates at once,
otherwise it waits in ``pending_validation`` for a human. Escalating goes through the ``support.incidents``
port — there is no incident table here: a repeated anomaly with the same fingerprint attaches its evidence
to the incident already open for it. When the port is missing or failing the anomaly stays
``pending_validation`` and is retried on the next run.
"""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.health import INCIDENTS
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.observability.detectors.rules import Finding
from portalab.modules.observability.models import Anomaly
from portalab.modules.observability.observability import log, metrics
from portalab.modules.observability.settings import ObservabilityConfig

OPEN = ("candidate", "pending_validation", "escalated")
_RANK = {"info": 0, "warning": 1, "critical": 2}


class AnomalyNotFound(NotFound):
    default_code = "observability.anomaly_not_found"


class AnomalyClosed(Conflict):
    default_code = "observability.anomaly_closed"


def anomaly_out(row: Anomaly) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "detector": row.detector,
        "component": row.component,
        "severity": row.severity,
        "status": row.status,
        "detected_at": row.detected_at.isoformat(),
        "last_seen_at": row.last_seen_at.isoformat(),
        "occurrences": row.occurrences,
        "evidence": row.evidence,
        "incident_ref": row.incident_ref,
    }


class EscalationService:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        config: Callable[[], ObservabilityConfig],
        *,
        clock: Clock | None = None,
        on_anomaly: Callable[[Anomaly], Any] | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.audit = audit
        self.capabilities = capabilities
        self.config = config
        self.clock = clock
        self.on_anomaly = on_anomaly

    def _incidents(self) -> Any:
        providers = self.capabilities.system_providers(INCIDENTS)
        return providers[0].provider if providers else None

    def _auto(self, severity: str) -> bool:
        cfg = self.config()
        return not cfg.escalation_require_validation and _RANK.get(severity, 0) >= _RANK.get(
            cfg.escalation_auto_severity, 2
        )

    async def observe(self, findings: list[Finding]) -> list[Anomaly]:
        touched: list[Anomaly] = []
        now = utc_now(self.clock)
        for finding in findings:
            async with self.database.unit_of_work() as uow:
                row = (
                    await uow.session.execute(
                        select(Anomaly)
                        .where(Anomaly.fingerprint == finding.fingerprint, Anomaly.status.in_(OPEN))
                        .order_by(Anomaly.detected_at.desc())
                        .limit(1)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if row is not None:
                    row.occurrences += 1
                    row.last_seen_at = now
                    row.evidence = {**finding.evidence, "summary": finding.summary}
                    if _RANK[finding.severity] > _RANK.get(row.severity, 0):
                        row.severity = finding.severity
                    touched.append(row)
                    continue
                row = Anomaly(
                    detector=finding.detector,
                    component=finding.component,
                    fingerprint=finding.fingerprint,
                    severity=finding.severity,
                    status="pending_validation",
                    detected_at=now,
                    last_seen_at=now,
                    occurrences=1,
                    evidence={**finding.evidence, "summary": finding.summary},
                    escalation_attempts=0,
                )
                uow.session.add(row)
                await uow.session.flush()
                await self.events.publish(
                    uow.session,
                    "observability.anomaly_detected",
                    {
                        "anomaly_id": str(row.id),
                        "detector": row.detector,
                        "component": row.component,
                        "severity": row.severity,
                    },
                    occurred_at=now,
                    subject=SubjectRef("anomaly", str(row.id)),
                    source="observability",
                )
                metrics.increment("observability.anomalies")
                touched.append(row)
                if self.on_anomaly is not None:
                    await self.on_anomaly(row)
        for row in touched:
            if row.status == "escalated" or (row.status == "pending_validation" and self._auto(row.severity)):
                await self.escalate(row.id)
        return touched

    async def escalate(self, anomaly_id: UUID) -> Anomaly:
        """Create or extend the incident for this anomaly; idempotent per fingerprint."""
        port = self._incidents()
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(Anomaly, anomaly_id, with_for_update=True)
            if row is None:
                raise AnomalyNotFound("No such anomaly.")
            evidence = {
                "anomaly_id": str(row.id),
                "detector": row.detector,
                "component": row.component,
                "occurrences": row.occurrences,
                **row.evidence,
            }
            if port is None:
                row.status, row.escalation_attempts = "pending_validation", row.escalation_attempts + 1
                return row
            try:
                incident_ref = row.incident_ref or await self._open_incident_for(uow.session, row)
                attached = await port.attach(incident_ref, evidence) if incident_ref else None
                if attached is None:
                    created = await port.create(
                        title=f"{row.detector.replace('_', ' ')} on {row.component}",
                        source="observability",
                        severity=row.severity,
                        evidence=evidence,
                    )
                    incident_ref = created.id
            except Exception:
                row.status, row.escalation_attempts = "pending_validation", row.escalation_attempts + 1
                log.warning(
                    "incident port unavailable; anomaly kept for retry",
                    extra={"fields": {"anomaly_id": str(row.id)}},
                )
                return row
            row.incident_ref, row.status = incident_ref, "escalated"
            return row

    async def _open_incident_for(self, session: Any, row: Anomaly) -> str | None:
        ref = (
            await session.execute(
                select(Anomaly.incident_ref)
                .where(Anomaly.fingerprint == row.fingerprint, Anomaly.incident_ref.is_not(None))
                .order_by(Anomaly.last_seen_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return str(ref) if ref else None

    async def retry_pending(self) -> int:
        """Retry escalations that failed because the incident port was down (validated or automatic)."""
        async with self.database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(Anomaly).where(
                            Anomaly.status == "pending_validation", Anomaly.escalation_attempts > 0
                        )
                    )
                )
                .scalars()
                .all()
            )
        retried = 0
        for row in rows:
            if row.validated_by is not None or self._auto(row.severity):
                await self.escalate(row.id)
                retried += 1
        return retried

    async def decide(self, actor: Principal, anomaly_id: UUID, decision: str) -> Anomaly:
        """Human decision on an anomaly: ``validate`` (escalate) or ``dismiss`` — audited."""
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(Anomaly, anomaly_id, with_for_update=True)
            if row is None:
                raise AnomalyNotFound("No such anomaly.")
            if row.status not in ("candidate", "pending_validation"):
                raise AnomalyClosed("This anomaly was already decided.")
            if decision == "dismiss":
                row.status = "dismissed"
            row.validated_by = actor.user_id
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action=f"observability.anomaly_{decision}",
                    actor=actor,
                    resource=ResourceRef("anomaly", str(row.id)),
                    decision="allow",
                    result="success",
                    context={"detector": row.detector, "component": row.component},
                    sensitive=True,
                ),
            )
        if decision == "validate":
            row = await self.escalate(anomaly_id)
            if row.status != "escalated":
                async with self.database.unit_of_work() as uow:
                    stored = await uow.session.get(Anomaly, anomaly_id, with_for_update=True)
                    if stored is not None and stored.escalation_attempts == 0:
                        stored.escalation_attempts = 1  # remember the validation for retries
        return row

    async def anomalies(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        async with self.database.session() as session:
            statement = select(Anomaly).order_by(Anomaly.last_seen_at.desc()).limit(limit)
            if status:
                statement = statement.where(Anomaly.status == status)
            return [anomaly_out(row) for row in (await session.execute(statement)).scalars()]
