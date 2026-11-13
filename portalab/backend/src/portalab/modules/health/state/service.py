"""State service (T007): gathers the deriver's inputs, writes ``service_state`` + ``state_history`` and
emits ``service.status_changed`` (``dimension="health"``) once per transition, deduplicated by
``(service, dimension, to_state, state_seq)``. Re-evaluation is idempotent: same inputs, no new row."""

from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.health import (
    INCIDENT_SEVERITY,
    INCIDENTS,
    SERVICE_DIRECTORY,
    AlertRule,
    ServiceInfo,
    alert_rule,
)
from portalab.capabilities.i18n import RESOLVER
from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, WithPermission
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.health.models import HealthSample, MaintenanceWindow, ServiceState, StateHistory
from portalab.modules.health.observability import log, metric_part, metrics
from portalab.modules.health.permissions import SERVICES_MANAGE, SERVICES_READ
from portalab.modules.health.settings import HealthConfig
from portalab.modules.health.state.deriver import RULES_VERSION, Derived, Inputs, Thresholds, derive

SYSTEM = Principal(channel="system")
RECENT = 20
# 027: an outage that lasts is announced at these durations (minutes) — automations act on it (« declare an
# incident when a service has been down for 10 minutes »)
LASTING_MINUTES = (5, 10, 15, 30, 60, 120)
OUTAGE_LASTING = "service.outage_lasting"


class StateService:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        *,
        config: HealthConfig | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.config = config or HealthConfig()
        self.clock = clock
        self._declared: set[str] = set()  # outages already turned into an incident (this process)
        self._told: set[str] = set()  # outages already announced (this process; the producer dedups too)

    def thresholds(self) -> Thresholds:
        return Thresholds(
            degraded_latency_ms=self.config.degraded_latency_ms,
            unavailable_after_failures=self.config.unavailable_after_failures,
            stale_after_seconds=self.config.stale_after_seconds,
        )

    def directory(self) -> Any:
        providers = self.capabilities.system_providers(SERVICE_DIRECTORY)
        return providers[0].provider if providers else None

    async def service_info(self, service_id: str) -> ServiceInfo | None:
        directory = self.directory()
        return await directory.service(service_id) if directory else None

    async def services(self) -> list[ServiceInfo]:
        directory = self.directory()
        return await directory.services() if directory else []

    async def active_maintenance(self, session: AsyncSession, service_id: str) -> MaintenanceWindow | None:
        return (
            await session.execute(
                select(MaintenanceWindow)
                .where(
                    MaintenanceWindow.status == "active",
                    or_(MaintenanceWindow.service_id == service_id, MaintenanceWindow.service_id.is_(None)),
                )
                .order_by(MaintenanceWindow.starts_at)
                .limit(1)
            )
        ).scalar_one_or_none()

    async def inputs(self, session: AsyncSession, service_id: str, now: datetime) -> tuple[Inputs, Any]:
        info = await self.service_info(service_id)
        samples = (
            (
                await session.execute(
                    select(HealthSample)
                    .where(HealthSample.service_id == service_id, HealthSample.checked_at <= now)
                    .order_by(HealthSample.checked_at.desc())
                    .limit(RECENT)
                )
            )
            .scalars()
            .all()
        )
        failures = 0
        for sample in samples:
            if sample.ok:
                break
            failures += 1
        maintenance = await self.active_maintenance(session, service_id)
        last = samples[0] if samples else None
        return (
            Inputs(
                now=now,
                connection_state=info.state if info else None,
                last_check_at=last.checked_at if last else None,
                last_ok=last.ok if last else None,
                last_latency_ms=last.latency_ms if last else None,
                consecutive_failures=failures,
                maintenance_active=maintenance is not None,
                last_warning=bool(last and last.ok and last.error_code),
            ),
            maintenance,
        )

    async def evaluate(self, service_id: str, *, occurred_at: datetime | None = None) -> Derived:
        now = utc_now(self.clock)
        outage: tuple[int, datetime, int] | None = None  # (state_seq, since, failed probes)
        back: tuple[int, datetime] | None = None  # the outage that ended (state_seq, since)
        recovered = False
        async with self.database.unit_of_work() as uow:
            session = uow.session
            inputs, maintenance = await self.inputs(session, service_id, now)
            derived = derive(inputs, self.thresholds())
            row = await session.get(ServiceState, service_id, with_for_update=True)
            last_ok_at = inputs.last_check_at if inputs.last_ok else None
            if row is None:
                row = ServiceState(
                    service_id=service_id,
                    state=derived.state,
                    state_since=occurred_at or now,
                    state_seq=0,
                    reason=derived.reason,
                    rules_version=RULES_VERSION,
                )
                session.add(row)
                before: str | None = None
                changed = True
            else:
                before = row.state
                changed = row.state != derived.state
            row.last_check_at = inputs.last_check_at
            if last_ok_at is not None:
                row.last_ok_at = last_ok_at
            row.maintenance_id = maintenance.id if maintenance else None
            if not changed:
                row.reason = derived.reason
                if derived.state == "unavailable":
                    await self._lasting(session, row, inputs, now)
                    outage = (row.state_seq, row.state_since, inputs.consecutive_failures)
            else:
                at = occurred_at or now
                recovered = derived.state == "operational" and before in ("unavailable", "degraded")
                if before == "unavailable" and derived.state in ("operational", "degraded"):
                    back = (row.state_seq, row.state_since)
                await self._transition(session, row, service_id, before, derived, at, now)
                if derived.state == "unavailable":
                    outage = (row.state_seq, row.state_since, inputs.consecutive_failures)
        # 027: what an outage does follows the service's alerting rule — an incident and a notification
        # once it lasts, the incident closed and an « it is back » notice when the service answers again
        if outage is not None:
            await self._outage(service_id, *outage, now)
        if back is not None:
            await self._back(service_id, *back, now)
        if recovered:
            await self._auto_resolve(service_id)
        return derived

    async def _transition(
        self,
        session: AsyncSession,
        row: ServiceState,
        service_id: str,
        before: str | None,
        derived: Derived,
        at: datetime,
        now: datetime,
    ) -> None:
        row.state, row.reason, row.state_since = derived.state, derived.reason, at
        row.state_seq += 1
        row.rules_version = RULES_VERSION
        await session.flush()
        session.add(
            StateHistory(
                service_id=service_id,
                from_state=before,
                to_state=derived.state,
                occurred_at=at,
                received_at=now,
                reason=derived.reason,
            )
        )
        await self.events.publish(
            session,
            "service.status_changed",
            {
                "service_id": service_id,
                "dimension": "health",
                "from_state": before,
                "to_state": derived.state,
                "state_seq": row.state_seq,
                "reason": derived.reason,
            },
            occurred_at=at,
            actor=SYSTEM,
            subject=SubjectRef("service", service_id),
            source="health",
        )
        metrics.increment(f"health.state_changes.{metric_part(derived.state)}")

    def incidents(self) -> Any:
        providers = self.capabilities.system_providers(INCIDENTS)
        return providers[0].provider if providers else None

    async def _language(self) -> str:
        try:
            providers = self.capabilities.system_providers(RESOLVER)
            if providers:
                return str((await providers[0].provider.for_user(None)).language or "en")
        except Exception:  # noqa: S110 — the default language is fine
            pass
        return "en"

    def rule(self, info: ServiceInfo | None) -> AlertRule:
        """027: the alerting rule in force for a service (its importance's, with its own overrides)."""
        if info is None:
            return alert_rule(self.config.alert_rules, "major")
        return alert_rule(self.config.alert_rules, info.importance, info.alerting)

    async def _outage(self, service_id: str, seq: int, since: datetime, failures: int, now: datetime) -> None:
        info = await self.service_info(service_id)
        rule = self.rule(info)
        minutes = (now - since).total_seconds() / 60
        if rule.incident and minutes >= rule.incident_after:
            await self._auto_incident(service_id, info, seq, minutes, failures)
        if minutes >= rule.notify_after:
            await self._announce(
                service_id, info, rule, seq, minutes, back=False, since=since, failures=failures
            )

    async def _back(self, service_id: str, seq: int, since: datetime, now: datetime) -> None:
        """The outage ended: those who were told it was down are told it is back."""
        info = await self.service_info(service_id)
        rule = self.rule(info)
        minutes = (now - since).total_seconds() / 60
        if minutes >= rule.notify_after:
            await self._announce(service_id, info, rule, seq, minutes, back=True, since=since)

    async def _announce(
        self,
        service_id: str,
        info: ServiceInfo | None,
        rule: AlertRule,
        seq: int,
        minutes: float,
        *,
        back: bool,
        since: datetime | None = None,
        failures: int = 0,
    ) -> None:
        """One notification per outage and audience: administrators (services.manage) and members
        (services.read, administrators apart), each by e-mail too when the rule says so."""
        key = f"{'back' if back else 'outage'}:{service_id}:{seq}"
        if key in self._told:
            return
        providers = self.capabilities.system_providers(NOTIFY)
        if not providers:
            return
        name = info.name if info is not None else service_id
        importance = info.importance if info is not None else "major"
        audiences = []
        if rule.notify_admins:
            audiences.append(("admins", WithPermission(SERVICES_MANAGE, (service_id,)), rule.email_admins))
        if rule.notify_members:
            members = WithPermission(SERVICES_READ, (service_id,), without=SERVICES_MANAGE)
            audiences.append(("members", members, rule.email_members))
        for audience_key, audience, email in audiences:
            try:
                await providers[0].provider.send(
                    CommunicationRequest(
                        category="system.health_email" if email else "system.health",
                        template_key=f"notifications:service.{'back' if back else 'unavailable'}",
                        audience=audience,
                        dedup_key=f"{key}:{audience_key}",
                        kind="notification" if back else "alert",
                        priority="normal" if back else ("critical" if importance == "critical" else "high"),
                        # issue 398: since when, how many checks failed, how much it matters
                        params={
                            "service": name,
                            "minutes": max(1, round(minutes)),
                            "since": since.isoformat() if since else "none",
                            "failures": failures,
                            "importance": importance,
                        },
                        source="module",
                        subject_ref=f"service:{service_id}",
                        required_permission=audience.permission,
                        action_url=f"/services/{service_id}",
                    )
                )
            except Exception as exc:
                log.warning("outage notification not sent", extra={"fields": {"error": type(exc).__name__}})
        self._told.add(key)
        metrics.increment(f"health.notifications.{'back' if back else 'outage'}")

    async def _auto_incident(
        self, service_id: str, info: ServiceInfo | None, seq: int, minutes: float, failures: int
    ) -> None:
        """027: a service unavailable for longer than its rule's delay gets an incident — once per outage
        (``outage:<service>:<seq>``), with its importance's severity."""
        key = f"outage:{service_id}:{seq}"
        if key in self._declared:
            return
        port = self.incidents()
        if port is None:
            return
        name = info.name if info is not None else service_id
        french = (await self._language()).startswith("fr")
        title = f"{name} ne répond plus" if french else f"{name} is not responding"
        summary = (
            f"{name} est injoignable depuis {int(minutes)} minutes ({failures} vérifications échouées)."
            if french
            else f"{name} has been unreachable for {int(minutes)} minutes ({failures} failed checks)."
        )
        try:
            await port.create(
                title=title,
                source="health",
                severity=INCIDENT_SEVERITY.get(info.importance if info else "major", "major"),
                evidence={"service_id": service_id, "state_seq": seq, "failures": failures},
                service_ids=[service_id],
                dedup_key=key,
                summary=summary,
                banner=self.rule(info).banner,
            )
            self._declared.add(key)
            metrics.increment("health.incidents.declared")
        except Exception as exc:
            log.warning("automatic incident not declared", extra={"fields": {"error": type(exc).__name__}})

    async def _auto_resolve(self, service_id: str) -> None:
        """027: the service is back — the incidents the portal declared for it are closed (not the ones a
        person opened), unless its rule keeps them open."""
        info = await self.service_info(service_id)
        port = self.incidents()
        resolve = getattr(port, "resolve_for_service", None)
        if info is None or not self.rule(info).auto_resolve or resolve is None:
            return
        french = (await self._language()).startswith("fr")
        message = (
            f"{info.name} répond de nouveau : incident clôturé automatiquement."
            if french
            else f"{info.name} answers again: incident closed automatically."
        )
        try:
            if await resolve(service_id, source="health", message=message):
                metrics.increment("health.incidents.resolved")
        except Exception as exc:
            log.warning("automatic incident not resolved", extra={"fields": {"error": type(exc).__name__}})

    async def _lasting(self, session: AsyncSession, row: ServiceState, inputs: Inputs, now: datetime) -> None:
        """027: how long the current outage has lasted, once per milestone (5, 10, 15, 30, 60, 120 min)."""
        minutes = (now - row.state_since).total_seconds() / 60
        reached = [m for m in LASTING_MINUTES if minutes >= m]
        if not reached:
            return
        info = await self.service_info(row.service_id)
        for milestone in reached:
            await self.events.publish(
                session,
                OUTAGE_LASTING,
                {
                    "service_id": row.service_id,
                    "service_label": info.name if info else None,
                    "state_seq": row.state_seq,
                    "minutes": milestone,
                    "failures": inputs.consecutive_failures,
                    "since": row.state_since.isoformat(),
                },
                occurred_at=now,
                actor=SYSTEM,
                subject=SubjectRef("service", row.service_id),
                source="health",
                dedup_key=f"{OUTAGE_LASTING}:{row.service_id}:{row.state_seq}:{milestone}",
            )

    async def evaluate_all(self) -> int:
        """Re-derive every known service (sweeps, maintenance transitions, start-up)."""
        known = {info.id for info in await self.services()}
        async with self.database.session() as session:
            known |= set((await session.execute(select(ServiceState.service_id))).scalars())
        for service_id in sorted(known):
            await self.evaluate(service_id)
        return len(known)
