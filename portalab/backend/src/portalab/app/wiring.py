"""Module wiring at the composition root: build each module from the kernel services.

Order matters: authorization (spec 003) first — it provides the Authorizer engine, the database ``AuditSink``
and the ``authz.admin_authority`` capability — then identity (spec 002), which consumes them. The event
publisher is the kernel outbox until the Events module (spec 007) replaces it.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditSink, LogAuditSink
from portalab.core.authz_port import Authorizer, DenyAllAuthorizer, Principal, ResourceRef
from portalab.core.blobstore import FileSystemBlobStore
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, OutboxEventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.modules.authz.module import AuthzModule
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.module import IdentityModule
from portalab.modules.privacy.module import PrivacyModule


class DeferredAuthorizer:
    """Delegates to an authorizer installed later (the database is only known at application start-up)."""

    def __init__(self) -> None:
        self.target: Authorizer = DenyAllAuthorizer()

    async def is_allowed(
        self, principal: Principal, permission: str, resource: ResourceRef | None = None
    ) -> bool:
        return await self.target.is_allowed(principal, permission, resource)


def wire_authz(database: Database, events: EventPublisher, capabilities: CapabilityRegistry) -> AuthzModule:
    module = AuthzModule(database, events, capabilities)
    module.register_capabilities()
    return module


def default_identity_context(
    database: Database,
    *,
    data_dir: Path,
    capabilities: CapabilityRegistry,
    authorizer: Authorizer,
    audit: AuditSink | None = None,
    events: EventPublisher | None = None,
) -> IdentityContext:
    return IdentityContext(
        database=database,
        events=events or OutboxEventPublisher(),
        audit=audit or LogAuditSink(),
        capabilities=capabilities,
        blobs=FileSystemBlobStore(data_dir / "blobs"),
        authorizer=authorizer,
    )


def wire_identity(context: IdentityContext, *, jobs: JobRegistry | None = None) -> IdentityModule:
    module = IdentityModule(context)
    module.register_capabilities()
    if jobs is not None:
        module.register_jobs(jobs)
    return module


@dataclass
class Platform:
    authz: AuthzModule
    privacy: PrivacyModule
    identity: IdentityModule
    seeds: list[Callable[[], Awaitable[None]]]

    async def seed_periodic_jobs(self) -> None:
        for seed in self.seeds:
            await seed()


def wire_platform(
    database: Database,
    *,
    data_dir: Path,
    capabilities: CapabilityRegistry,
    jobs: JobRegistry | None = None,
) -> Platform:
    """Production wiring shared by ``serve``, ``worker`` and the CLI."""
    events = OutboxEventPublisher()
    authz = wire_authz(database, events, capabilities)
    privacy = PrivacyModule(database, events, authz.audit, capabilities)
    privacy.register_capabilities()
    context = default_identity_context(
        database,
        data_dir=data_dir,
        capabilities=capabilities,
        authorizer=authz.engine,
        audit=authz.audit,
        events=events,
    )
    context.visibility = privacy.filter
    identity = wire_identity(context, jobs=jobs)
    seeds: list[Callable[[], Awaitable[None]]] = []
    if jobs is not None:
        seeds.extend(privacy.register_jobs(jobs))
        seeds.append(
            register_periodic(
                jobs,
                database,
                "audit.partition_maintenance",
                timedelta(days=1),
                lambda: authz.maintain_audit_partitions(privacy.config.audit_retention_months),
                owner="module:authz",
            )
        )
        seeds.append(
            register_periodic(
                jobs,
                database,
                "audit.checkpoint",
                timedelta(hours=1),
                authz.seal_audit_checkpoint,
                owner="module:authz",
            )
        )
        seeds.append(identity.ensure_sweeps_scheduled)
    return Platform(authz, privacy, identity, seeds)
