"""Administration module facade (spec 020): configuration store and policies, preferences facade and read
ports, toggles, import/export, first-run wizard, Control Center, admin surfaces."""

from typing import Any

from portalab.capabilities.administration import (
    CONFIG_WRITER_CAPABILITY,
    EXTENSION_STATE_CAPABILITY,
    PANEL_CAPABILITY,
    AdminSurface,
    default_admin_surfaces,
)
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.config import I18N_POLICY_READER, LOCALE_READER
from portalab.capabilities.plugins import TOGGLE_WRITER
from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.secrets import SecretBox
from portalab.core.time import Clock
from portalab.modules.administration import event_types as _event_types  # noqa: F401 — registers event types
from portalab.modules.administration import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.administration import settings as _settings  # noqa: F401 — declares settings
from portalab.modules.administration.config.ports import (
    ConfigI18nPolicyReader,
    ConfigUserLocalePreferenceReader,
)
from portalab.modules.administration.config.registry import SettingRegistry
from portalab.modules.administration.config.service import Change, ConfigService
from portalab.modules.administration.config.user_prefs import (
    PreferenceErasureParticipant,
    PreferenceExportContributor,
    UserPreferences,
)
from portalab.modules.administration.firstrun.service import FirstRunService
from portalab.modules.administration.importexport.service import ImportExportService
from portalab.modules.administration.observability import metrics
from portalab.modules.administration.overview.panels import (
    AuditPanel,
    ConfigurationPanel,
    ServicesPanel,
    StoragePanel,
)
from portalab.modules.administration.overview.service import ControlCenter
from portalab.modules.administration.policies.service import PolicyService
from portalab.modules.administration.toggles.service import ToggleService

OWNER = "module:administration"


class _ExtensionState:
    def __init__(self, toggles: Any) -> None:
        self.toggles = toggles

    async def enabled(self, kind: str, ref: str) -> bool:
        return bool(await self.toggles.is_enabled(kind, ref))


class _ConfigWriter:
    def __init__(self, config: Any) -> None:
        self.config = config

    async def set_global(self, actor: Principal, key: str, value: Any, *, reason: str = "") -> None:
        await self.config.apply(
            [Change(key, value)], actor, admin_change=True, reason=reason or "admin change"
        )

    async def set_user(self, actor: Principal, key: str, value: Any) -> None:
        user = actor.acting_for or actor.user_id
        if user is None:
            raise ValueError("a user setting needs a user")
        await self.config.set(key, value, scope="user", scope_ref=str(user), actor=actor)


class AdministrationModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        secrets: SecretBox,
        *,
        registry: SettingRegistry | None = None,
        clock: Clock | None = None,
        panel_timeout_ms: int = 1500,
    ) -> None:
        self.database = database
        self.capabilities = capabilities
        self.registry = registry or SettingRegistry()
        self.config = ConfigService(database, self.registry, secrets, audit, events, clock=clock)
        self.policies = PolicyService(database, self.registry, audit, events, clock=clock)
        self.preferences = UserPreferences(self.config)
        self.toggles = ToggleService(database, capabilities, audit, events, clock=clock)
        self.import_export = ImportExportService(self.config, audit, events, clock=clock)
        self.first_run = FirstRunService(database, capabilities, self.config, audit, events, clock=clock)
        self.control_center = ControlCenter(capabilities, authorizer, timeout_ms=panel_timeout_ms)
        self.clock = clock

    def register_capabilities(self) -> None:
        provide = self.capabilities.provide
        provide(CONFIG, self.config, instance_ref="administration", owner=OWNER)
        provide(
            EXTENSION_STATE_CAPABILITY,
            _ExtensionState(self.toggles),
            instance_ref="administration",
            owner=OWNER,
        )
        provide(
            CONFIG_WRITER_CAPABILITY, _ConfigWriter(self.config), instance_ref="administration", owner=OWNER
        )
        provide(TOGGLE_WRITER, self.toggles, instance_ref="administration", owner=OWNER)
        provide(
            LOCALE_READER,
            ConfigUserLocalePreferenceReader(self.config),
            instance_ref="administration",
            owner=OWNER,
        )
        provide(
            I18N_POLICY_READER,
            ConfigI18nPolicyReader(self.config),
            instance_ref="administration",
            owner=OWNER,
        )
        provide(
            ERASURE_CAPABILITY,
            PreferenceErasureParticipant(self.config),
            instance_ref="administration.preferences",
            owner=OWNER,
        )
        provide(
            EXPORT_CAPABILITY,
            PreferenceExportContributor(self.config),
            instance_ref="administration.preferences",
            owner=OWNER,
        )
        panels = (
            (
                "configuration",
                ConfigurationPanel(self.first_run, self.policies, metrics.snapshot),
                "configuration.manage",
                10,
            ),
            ("services", ServicesPanel(self.capabilities), "infrastructure.read", 30),
            ("storage", StoragePanel(self.database, self.clock), "infrastructure.read", 40),
            ("audit", AuditPanel(self.capabilities), "audit.read", 50),
        )
        for name, provider, permission, order in panels:
            provide(
                PANEL_CAPABILITY,
                provider,
                instance_ref=f"administration.{name}",
                owner=OWNER,
                metadata={"panel": name, "permission": permission, "order": order},
            )
        default_admin_surfaces.register(
            AdminSurface(
                "configuration", "admin.surface.configuration", "/admin/config", "configuration.manage", OWNER
            )
        )
        default_admin_surfaces.register(
            AdminSurface("extensions", "admin.surface.extensions", "/admin/toggles", "modules.manage", OWNER)
        )
