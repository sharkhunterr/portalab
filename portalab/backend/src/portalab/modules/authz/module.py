"""Authorization module facade: engine, catalog, grants, Admin authority, audit store, confirmations."""

from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.user_grants import CAPABILITY as USER_GRANTS
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.permissions import PermissionRegistry, default_permissions
from portalab.core.time import Clock
from portalab.modules.authz.admin_authority.service import AdminAuthorityService, register_admin_authority
from portalab.modules.authz.audit.store import DatabaseAuditSink
from portalab.modules.authz.catalog import core_permissions  # noqa: F401 — declares the core catalog
from portalab.modules.authz.catalog.sync import CatalogSync
from portalab.modules.authz.confirmation.service import ConfirmationService
from portalab.modules.authz.engine.engine import AuthorizationEngine
from portalab.modules.authz.grants.service import GrantService
from portalab.modules.authz.grants.user_grants import UserGrantsProvider
from portalab.modules.authz.settings import AuthzConfig

OWNER = "module:authz"


class AuthzModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        *,
        registry: PermissionRegistry = default_permissions,
        config: AuthzConfig | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.config = config or AuthzConfig()
        self.database = database
        self.capabilities = capabilities
        self.audit = DatabaseAuditSink(
            database, max_context_bytes=self.config.audit_context_max_bytes, clock=clock
        )
        self.catalog = CatalogSync(database, registry, clock)
        self.admin_authority = AdminAuthorityService(database, self.audit, events, clock=clock)
        self.engine = AuthorizationEngine(database, self.catalog, self.audit, events, clock=clock)
        self.grants = GrantService(database, self.audit, events, self.admin_authority, clock=clock)
        self.confirmations = ConfirmationService(
            database, ttl_seconds=self.config.confirmation_ttl_seconds, clock=clock
        )

    def register_capabilities(self) -> None:
        register_admin_authority(self.capabilities, self.admin_authority)
        self.capabilities.provide(
            USER_GRANTS, UserGrantsProvider(self.grants), instance_ref="authz", owner=OWNER
        )
