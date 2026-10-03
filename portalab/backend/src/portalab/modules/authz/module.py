"""Authorization module facade: engine, catalog, grants, Admin authority, audit store, confirmations."""

from uuid import UUID

from portalab.capabilities.administration import AUDIT_STATUS_CAPABILITY as AUDIT_STATUS
from portalab.capabilities.administration import PLUGIN_PERMISSIONS_CAPABILITY as PLUGIN_PERMISSIONS
from portalab.capabilities.administration import AdminSurface, default_admin_surfaces
from portalab.capabilities.confirmations import CAPABILITY as CONFIRMATIONS
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.user_grants import CAPABILITY as USER_GRANTS
from portalab.capabilities.user_grants import ROLES_CAPABILITY as ROLES
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.permissions import PermissionRegistry, default_permissions
from portalab.core.time import Clock, utc_now
from portalab.modules.authz import event_types as _event_types  # noqa: F401 — registers event types
from portalab.modules.authz.admin_authority.service import AdminAuthorityService, register_admin_authority
from portalab.modules.authz.audit.query import AuditQuery
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
        self.audit_query = AuditQuery(database, self.audit, self.engine)
        self.events = events
        self.clock = clock
        self.confirmations = ConfirmationService(
            database, ttl_seconds=self.config.confirmation_ttl_seconds, clock=clock
        )

    def register_capabilities(self) -> None:
        register_admin_authority(self.capabilities, self.admin_authority)
        self.capabilities.provide(
            USER_GRANTS, UserGrantsProvider(self.grants), instance_ref="authz", owner=OWNER
        )
        self.capabilities.provide(CONFIRMATIONS, self.confirmations, instance_ref="authz", owner=OWNER)
        self.capabilities.provide(ROLES, _UserRoles(self), instance_ref="authz", owner=OWNER)
        self.capabilities.provide(
            PLUGIN_PERMISSIONS, _PluginPermissions(self), instance_ref="authz", owner=OWNER
        )
        self.capabilities.provide(AUDIT_STATUS, _AuditStatus(self), instance_ref="authz", owner=OWNER)
        for key, route, permission in (
            ("roles", "/admin/roles", "users.roles.manage"),
            ("audit", "/admin/audit", "audit.read"),
        ):
            default_admin_surfaces.register(
                AdminSurface(key, f"admin.surface.{key}", route, permission, OWNER)
            )

    async def maintain_audit_partitions(self, retention_months: int | None) -> dict[str, list[str]]:
        """Create upcoming audit partitions, drop expired ones (spec 021 T019)."""
        from portalab.modules.authz.audit import partitions

        return await partitions.maintain(
            self.database, utc_now(self.clock), retention_months=retention_months
        )

    async def seal_audit_checkpoint(self) -> object:
        """Seal the next settled range of audit entries in the hash chain (spec 021 T020)."""
        from portalab.modules.authz.audit import checkpoints

        return await checkpoints.create_checkpoint(self.database, self.events, clock=self.clock)


class _PluginPermissions:
    def __init__(self, module: AuthzModule) -> None:
        self.module = module

    async def set_enabled(self, plugin_id: str, enabled: bool) -> int:
        from portalab.modules.authz.catalog.declare import set_plugin_permissions_enabled

        async with self.module.database.unit_of_work() as uow:
            return await set_plugin_permissions_enabled(uow.session, plugin_id, enabled)


class _AuditStatus:
    def __init__(self, module: AuthzModule) -> None:
        self.module = module

    async def status(self) -> dict[str, object]:
        from sqlalchemy import func, select

        from portalab.modules.authz.models import AuditCheckpoint, AuditEntry

        async with self.module.database.session() as session:
            last = (
                await session.execute(
                    select(AuditCheckpoint).order_by(AuditCheckpoint.to_seq.desc()).limit(1)
                )
            ).scalar_one_or_none()
            newest = await session.scalar(select(func.max(AuditEntry.seq)))
        return {
            "last_checkpoint_seq": last.to_seq if last else None,
            "last_checkpoint_at": last.created_at.isoformat() if last else None,
            "unsealed_entries": (newest or 0) - (last.to_seq if last else 0),
        }


class _UserRoles:
    def __init__(self, module: "AuthzModule") -> None:
        self.module = module

    async def roles_of(self, user_id: UUID) -> frozenset[str]:
        return frozenset({"user", *(role.key for role in await self.module.grants.user_roles(user_id))})
