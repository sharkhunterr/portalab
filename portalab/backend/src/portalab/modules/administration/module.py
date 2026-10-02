"""Administration module facade (spec 020): configuration store and policies, preferences facade and read
ports, toggles, import/export, first-run wizard, Control Center, admin surfaces."""

from portalab.capabilities.administration import PANEL_CAPABILITY, AdminSurface, default_admin_surfaces
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.config import I18N_POLICY_READER, LOCALE_READER
from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Authorizer
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.secrets import SecretBox
from portalab.core.time import Clock
from portalab.modules.administration import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.administration import settings as _settings  # noqa: F401 — declares settings
from portalab.modules.administration.config.ports import (
    ConfigI18nPolicyReader,
    ConfigUserLocalePreferenceReader,
)
from portalab.modules.administration.config.registry import SettingRegistry
from portalab.modules.administration.config.service import ConfigService
from portalab.modules.administration.config.user_prefs import (
    PreferenceErasureParticipant,
    PreferenceExportContributor,
    UserPreferences,
)
from portalab.modules.administration.firstrun.service import FirstRunService
from portalab.modules.administration.importexport.service import ImportExportService
from portalab.modules.administration.observability import metrics
from portalab.modules.administration.overview.panels import AuditPanel, ConfigurationPanel, PlaceholderPanel
from portalab.modules.administration.overview.service import ControlCenter
from portalab.modules.administration.policies.service import PolicyService
from portalab.modules.administration.toggles.service import ToggleService

OWNER = "module:administration"


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

    def register_capabilities(self) -> None:
        provide = self.capabilities.provide
        provide(CONFIG, self.config, instance_ref="administration", owner=OWNER)
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
            ("health", PlaceholderPanel("025-observability"), "infrastructure.read", 20),
            ("infrastructure", PlaceholderPanel("006-health-maintenance"), "infrastructure.read", 30),
            ("storage", PlaceholderPanel("006-health-maintenance"), "infrastructure.read", 40),
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
