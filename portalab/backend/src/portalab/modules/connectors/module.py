"""Connectors module facade (spec 005): services, connection tests, discovery, sync, resync, purge hook."""

from typing import Any

from portalab.capabilities.administration import (
    FIRST_RUN_STEP_CAPABILITY,
    SECRETS_REKEY_CAPABILITY,
    TOGGLE_HOOK_CAPABILITY,
    AdminSurface,
    default_admin_surfaces,
)
from portalab.capabilities.automation_actions import ActionRegistry, default_actions
from portalab.capabilities.connector_sdk import ConnectorRegistry, default_connectors
from portalab.capabilities.health import SERVICE_DIRECTORY
from portalab.capabilities.record_sink import SinkRegistry, default_sinks
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.service_data import CAPABILITY as SERVICE_DATA
from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Authorizer, DenyAllAuthorizer
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.registry import JobRegistry
from portalab.core.secrets import SecretBox
from portalab.core.time import Clock
from portalab.modules.connectors import event_types as _event_types  # noqa: F401 — registers event types
from portalab.modules.connectors import settings as _settings  # noqa: F401 — declares settings
from portalab.modules.connectors.automation import ConnectorActions, register_actions
from portalab.modules.connectors.data import ServiceDataOwner
from portalab.modules.connectors.directory import ConnectorServiceDirectory
from portalab.modules.connectors.discovery.service import DiscoveryService
from portalab.modules.connectors.firstrun import STEP, ServicesFirstRunStep
from portalab.modules.connectors.permissions import SERVICES_READ
from portalab.modules.connectors.retention import register_targets
from portalab.modules.connectors.services.compatibility import CompatibilityToggleHook
from portalab.modules.connectors.services.manager import ManagerHooks, ServiceManager
from portalab.modules.connectors.services.rekey import ServiceSecretsRekey
from portalab.modules.connectors.services.tester import ConnectionTester
from portalab.modules.connectors.settings import ConnectorsConfig
from portalab.modules.connectors.sync.reconcile import FieldPriorities
from portalab.modules.connectors.sync.resync import ResyncService
from portalab.modules.connectors.sync.runner import SyncRunner
from portalab.modules.connectors.sync.scheduler import SyncScheduler

OWNER = "module:connectors"


class ConnectorsModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        secret_box: SecretBox,
        *,
        authorizer: Authorizer | None = None,
        connectors: ConnectorRegistry = default_connectors,
        sinks: SinkRegistry = default_sinks,
        actions: ActionRegistry = default_actions,
        config: ConnectorsConfig | None = None,
        clock: Clock | None = None,
        hooks: ManagerHooks | None = None,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.connectors = connectors
        self.sinks = sinks
        self.actions = actions
        self.authorizer = authorizer or DenyAllAuthorizer()
        self.manager = ServiceManager(
            database,
            events,
            audit,
            capabilities,
            connectors,
            secret_box,
            config=config,
            clock=clock,
            hooks=hooks,
        )
        self.tester = ConnectionTester(self.manager)
        self.discovery = DiscoveryService(self.manager)
        self.runner = SyncRunner(self.manager, sinks)
        self.scheduler = SyncScheduler(self.runner)
        self.resync = ResyncService(self.scheduler)
        self.data = ServiceDataOwner(self.manager, sinks)
        self.priorities = FieldPriorities(capabilities)

    @property
    def config(self) -> ConnectorsConfig:
        return self.manager.config

    @config.setter
    def config(self, value: ConnectorsConfig) -> None:
        self.manager.config = value
        self.manager.breakers.configure(
            threshold=value.circuit_failure_threshold, open_seconds=value.circuit_open_seconds
        )

    def register_capabilities(self) -> None:
        self.manager.declare_specs()
        self.capabilities.provide(SERVICE_DATA, self.data, instance_ref="connectors", owner=OWNER)
        self.capabilities.provide(
            SERVICE_DIRECTORY, ConnectorServiceDirectory(self.manager), instance_ref="connectors", owner=OWNER
        )
        self.capabilities.provide(
            TOGGLE_HOOK_CAPABILITY,
            CompatibilityToggleHook(self.manager.checker, self.manager.connector_key_of),
            instance_ref="connectors",
            owner=OWNER,
        )
        self.capabilities.provide(
            SECRETS_REKEY_CAPABILITY, ServiceSecretsRekey(), instance_ref="connectors", owner=OWNER
        )
        self.capabilities.provide(
            FIRST_RUN_STEP_CAPABILITY,
            ServicesFirstRunStep(self.manager),
            instance_ref=STEP,
            owner=OWNER,
            metadata={"step": STEP, "skippable": True},
        )
        default_admin_surfaces.register(
            AdminSurface("services", "admin.surface.services", "/admin/services", SERVICES_READ, OWNER)
        )
        register_actions(self.actions, ConnectorActions(self.scheduler, self.authorizer))
        register_targets()

    def register_jobs(self, jobs: JobRegistry) -> Any:
        return self.scheduler.register(jobs)

    async def start(self) -> int:
        """Rebuild this process's capability providers from the stored service states."""
        return await self.manager.restore()
