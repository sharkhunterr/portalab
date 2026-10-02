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
from portalab.core.secrets import SecretBox
from portalab.modules.administration.module import AdministrationModule
from portalab.modules.authz.module import AuthzModule
from portalab.modules.connectors.module import ConnectorsModule
from portalab.modules.events.module import EventsModule
from portalab.modules.events.publisher.publisher import EventStorePublisher
from portalab.modules.health.module import HealthModule
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.module import IdentityModule
from portalab.modules.observability.module import ObservabilityModule
from portalab.modules.privacy.module import PrivacyModule
from portalab.modules.ui.module import UiModule


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
    administration: AdministrationModule
    identity: IdentityModule
    events: EventsModule
    connectors: ConnectorsModule
    health: HealthModule
    observability: ObservabilityModule
    ui: UiModule
    seeds: list[Callable[[], Awaitable[None]]]

    async def seed_periodic_jobs(self) -> None:
        for seed in self.seeds:
            await seed()

    async def refresh_config(self) -> bool:
        from portalab.app.config_bindings import safe_refresh

        return await safe_refresh(self)

    async def start_services(self) -> bool:
        """Provide the capabilities of the enabled services in this process (spec 005)."""
        try:
            await self.connectors.start()
        except Exception:
            return False
        return True


def wire_platform(
    database: Database,
    *,
    data_dir: Path,
    capabilities: CapabilityRegistry,
    secret_key: bytes,
    jobs: JobRegistry | None = None,
) -> Platform:
    """Production wiring shared by ``serve``, ``worker`` and the CLI."""
    events = EventStorePublisher()
    authz = wire_authz(database, events, capabilities)
    privacy = PrivacyModule(database, events, authz.audit, capabilities)
    privacy.register_capabilities()
    administration = AdministrationModule(
        database, events, authz.audit, capabilities, authz.engine, SecretBox(secret_key)
    )
    administration.register_capabilities()
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
    events_module = EventsModule(
        database, authz.audit, capabilities, visibility=privacy.filter, publisher=events
    )
    events_module.register()
    connectors = ConnectorsModule(
        database, events, authz.audit, capabilities, SecretBox(secret_key), authorizer=authz.engine
    )
    connectors.register_capabilities()
    health = HealthModule(database, events, authz.audit, capabilities)
    health.register_capabilities()
    observability = ObservabilityModule(database, events, authz.audit, capabilities)
    observability.register_capabilities()
    ui = UiModule(database, events, authz.audit, capabilities)
    ui.register()
    administration.registry.register_validator("ui.theme", ui.themes.choice_errors, owner="module:ui")
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
        seeds.append(connectors.register_jobs(jobs))
        seeds.extend(health.register_jobs(jobs))
        seeds.extend(observability.register_jobs(jobs))
    platform = Platform(
        authz, privacy, administration, identity, events_module, connectors, health, observability, ui, seeds
    )
    from portalab.app.config_bindings import bind

    bind(platform)
    return platform
