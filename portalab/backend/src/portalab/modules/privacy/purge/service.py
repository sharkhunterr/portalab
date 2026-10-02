"""Purge of a service's historized data (T029; FR-020..022, R9, CD-014).

Disconnecting a service never purges anything. A purge is a distinct action: ``services.purge`` (sensitive)
plus a single-use confirmation token bound to the exact service, then a job asks every
``connectors.service_data`` provider to remove that instance's rows (providers arrive with spec 005).
"""

from dataclasses import dataclass
from typing import Any

from portalab.capabilities.confirmations import CAPABILITY as CONFIRMATIONS
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.service_data import CAPABILITY as SERVICE_DATA
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, Forbidden, Unavailable
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.jobs.queue import enqueue
from portalab.core.time import Clock, utc_now
from portalab.modules.privacy.observability import metrics

PERMISSION = "services.purge"
JOB = "privacy.purge_service_data"


class ConfirmationRequired(Conflict):
    default_code = "authz.confirmation_required"
    default_title = "Confirmation required"


@dataclass(frozen=True, slots=True)
class PurgeRequested:
    service_id: str
    job_id: str


class ServicePurge:
    def __init__(
        self,
        database: Database,
        capabilities: CapabilityRegistry,
        audit: AuditSink,
        events: EventPublisher,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.audit = audit
        self.events = events
        self.clock = clock

    def _confirmations(self) -> Any:
        providers = self.capabilities.system_providers(CONFIRMATIONS)
        if not providers:
            raise Unavailable("Confirmations are not available.", code="authz.unavailable")
        return providers[0].provider

    async def request(self, principal: Principal, service_id: str, token: str | None) -> PurgeRequested:
        resource = ResourceRef("service", service_id)
        payload = {"action": "purge", "service_id": service_id}
        confirmations = self._confirmations()
        if token is None:
            issued = await confirmations.issue(principal, PERMISSION, resource, payload)
            raise ConfirmationRequired(
                "Purging deletes this service's history in the portal. Confirm to continue.",
                extensions={"confirmation": issued},  # one-time code, bound to this purge,
            )
        if not await confirmations.consume(token, principal, PERMISSION, resource, payload):
            raise Forbidden("The confirmation is invalid or expired.", code="authz.confirmation_invalid")
        async with self.database.unit_of_work() as uow:
            job = await enqueue(
                uow.session,
                kind=JOB,
                payload={"service_id": service_id},
                dedup_key=f"{JOB}:{service_id}:{utc_now(self.clock).strftime('%Y%m%dT%H%M%S')}",
                clock=self.clock,
            )
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action="service.purge_requested",
                    actor=principal,
                    resource=resource,
                    decision="allow",
                    result="success",
                    context={"service_id": service_id},
                    sensitive=True,
                ),
            )
        return PurgeRequested(service_id, str(job.job_id))

    async def run(self, service_id: str) -> int:
        removed = 0
        for registration in self.capabilities.system_providers(SERVICE_DATA):
            if await registration.provider.has_service(service_id):
                removed += int(await registration.provider.purge_service_data(service_id))
        async with self.database.unit_of_work() as uow:
            await self.events.publish(
                uow.session,
                "service.data_purged",
                {"service_id": service_id, "rows": removed},
                occurred_at=utc_now(self.clock),
                subject=SubjectRef("service", service_id),
                source="privacy",
            )
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action="service.data_purged",
                    actor=Principal(channel="system"),
                    resource=ResourceRef("service", service_id),
                    decision="n/a",
                    result="success",
                    context={"rows": removed},
                    sensitive=True,
                ),
            )
        metrics.increment("privacy.purge.rows", removed)
        return removed
