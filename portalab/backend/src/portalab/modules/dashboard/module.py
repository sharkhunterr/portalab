"""Dashboard module facade (spec 009): widget registry, policy overlay, instances, gateway, starter,
"Since Last Login", invalidation bridge and administration."""

from dataclasses import replace
from typing import Any

from portalab.capabilities.administration import CONFIG_WRITER_CAPABILITY
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.dashboard import WidgetRegistry, default_widgets
from portalab.capabilities.events import (
    ConsumerRegistry,
    EventTypeRegistry,
    default_consumers,
    default_event_types,
)
from portalab.capabilities.observability import (
    Check,
    CheckResult,
    ObservableRegistry,
    ObservedComponent,
    default_observables,
)
from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.errors import Unavailable, ValidationFailed
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock
from portalab.modules.dashboard import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.dashboard.conditions.evaluator import ConditionEvaluator
from portalab.modules.dashboard.events import register_event_types
from portalab.modules.dashboard.gateway.gateway import WidgetGateway
from portalab.modules.dashboard.invalidate.bridge import (
    CONSUMER as INVALIDATION,
)
from portalab.modules.dashboard.invalidate.bridge import (
    invalidation_consumer,
    watched_types,
)
from portalab.modules.dashboard.observability import metrics
from portalab.modules.dashboard.privacy import DashboardParticipant
from portalab.modules.dashboard.registry.plugin_widgets import (
    CONSUMER as PLUGIN_WIDGETS,
)
from portalab.modules.dashboard.registry.plugin_widgets import (
    plugin_state_consumer,
)
from portalab.modules.dashboard.service.service import DashboardService
from portalab.modules.dashboard.settings import POLICIES, SETTINGS, STARTER, DashboardConfig
from portalab.modules.dashboard.summary.aggregator import SinceLastLogin
from portalab.modules.dashboard.validators import DashboardValidators
from portalab.modules.dashboard.widgets.builtin import register_builtin

OWNER = "module:dashboard"


class DashboardModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        *,
        clock: Clock | None = None,
        registry: WidgetRegistry = default_widgets,
        event_types: EventTypeRegistry = default_event_types,
        consumers: ConsumerRegistry = default_consumers,
        observables: ObservableRegistry = default_observables,
    ) -> None:
        self.database = database
        self.audit = audit
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.clock = clock
        self.registry = registry
        self.config = DashboardConfig()
        self.gateway = WidgetGateway(registry, authorizer, capabilities, lambda: self.config, clock=clock)
        self.conditions = ConditionEvaluator(authorizer, capabilities, data_present=self.gateway.has_data)
        self.service = DashboardService(
            database, events, registry, self.gateway, self.conditions, lambda: self.config, clock=clock
        )
        self.summary = SinceLastLogin(database, registry, lambda: self.config, clock=clock)
        self.validators = DashboardValidators(registry)
        self.event_types = event_types
        self.consumers = consumers
        self.observables = observables

    def register(self) -> None:
        if self.registry.get("dashboard.welcome") is None:
            register_builtin(self.registry, self.capabilities, self.authorizer, self.clock)
        register_event_types(self.event_types)
        participant = DashboardParticipant(self.database, self.service.erase)
        for capability in (ERASURE_CAPABILITY, EXPORT_CAPABILITY):
            if not any(p.instance_ref == "dashboard" for p in self.capabilities.system_providers(capability)):
                self.capabilities.provide(capability, participant, instance_ref="dashboard", owner=OWNER)
        if self.consumers.get(PLUGIN_WIDGETS) is None:
            self.consumers.register(plugin_state_consumer(self.registry))
        types = watched_types(self.registry)
        if types and self.consumers.get(INVALIDATION) is None:
            self.consumers.register(
                invalidation_consumer(self.database, self.registry, types, clock=self.clock)
            )
        self.observables.declare(
            ObservedComponent(
                "dashboard", OWNER, label="Dashboard", functional_checks=(Check("widgets", self.probe),)
            )
        )

    # --- configuration --------------------------------------------------------------------------------
    async def refresh_config(self) -> None:
        providers = self.capabilities.system_providers(CONFIG)
        if not providers:
            return
        reader = providers[0].provider
        values = {field: (await reader.get(key)).value for field, key in SETTINGS.items()}
        self.config = replace(self.config, **values)

    async def admin_settings(self) -> dict[str, Any]:
        await self.refresh_config()
        return {
            "policies": self.config.widget_policies,
            "starter": self.config.starter_layout,
            "widgets": [
                {
                    "key": w.definition.key,
                    "title_key": w.definition.title_key,
                    "owner": w.owner,
                    "required_permission": w.definition.required_permission,
                    # 027: what the administration page needs to place it
                    "icon": w.definition.icon,
                    "size": {
                        "default": {"w": w.definition.size.default.w, "h": w.definition.size.default.h},
                        "min": {"w": w.definition.size.min.w, "h": w.definition.size.min.h},
                        "max": {"w": w.definition.size.max.w, "h": w.definition.size.max.h},
                    },
                    "sold": w.definition.product is not None,
                }
                for w in self.registry.widgets()
            ],
        }

    async def set_setting(self, principal: Principal, key: str, value: Any) -> None:
        validator = self.validators.table()[key]
        errors = await validator(value)
        if errors:
            raise ValidationFailed(
                "Invalid dashboard setting.", code="dashboard.invalid_policy", extensions={"errors": errors}
            )
        providers = self.capabilities.system_providers(CONFIG_WRITER_CAPABILITY)
        if not providers:
            raise Unavailable("Administration is not available.", code="admin.unavailable")
        await providers[0].provider.set_global(
            principal, key, value, reason="dashboard policy"
        )  # audited by 020
        await self.refresh_config()

    async def set_policies(self, principal: Principal, value: dict[str, Any]) -> None:
        await self.set_setting(principal, POLICIES, value)

    async def set_starter(self, principal: Principal, value: list[dict[str, Any]]) -> None:
        await self.set_setting(principal, STARTER, value)

    async def probe(self) -> CheckResult:
        """Functional check (025): every mandatory widget is registered (every dashboard can show it)."""
        mandatory = [
            k for k, p in self.config.widget_policies.items() if (p or {}).get("class") == "mandatory"
        ]
        missing = [k for k in mandatory if self.registry.get(k) is None]
        facts = {
            "widgets": len(self.registry.widgets()),
            "mandatory": len(mandatory),
            "missing": len(missing),
        }
        metrics.gauge("dashboard.widgets", len(self.registry.widgets()))
        if missing:
            return CheckResult("degraded", f"{len(missing)} mandatory widget(s) not registered", facts)
        return CheckResult("ok", "dashboard widgets registered", facts)
