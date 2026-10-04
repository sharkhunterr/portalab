"""Marketplace module facade (spec 015). Slice A: the community **funding lifecycle** — projects
registered by Community, the permissioned state machine with append-only history, funding reserved in
the 013 ledger with mandatory acknowledgement, resolution per frozen rules (release on failure, consume at
milestones), account-deletion handling (R6), reconciliation and notifications. Slice B: the catalog —
product types, versioned products, atomic acquisition with named conditions, activation, refunds, grants,
revocation, quota products (no paid priority), entitlements and integrations."""

from dataclasses import replace
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.ai import AIToolRegistry, default_ai_tools
from portalab.capabilities.community import SectionRegistry, default_sections
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.dashboard import ENTITLEMENTS, WidgetRegistry, default_widgets
from portalab.capabilities.events import EventTypeRegistry, default_event_types
from portalab.capabilities.marketplace import LIFECYCLE, ProductTypeRegistry, default_product_types
from portalab.capabilities.notifications import declare_category, default_categories
from portalab.capabilities.observability import (
    Check,
    CheckResult,
    ObservableRegistry,
    ObservedComponent,
    default_observables,
)
from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.search import SearchRegistry, default_search
from portalab.capabilities.themes import ENTITLEMENTS as THEME_ENTITLEMENTS
from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.permissions import PermissionRegistry, default_permissions
from portalab.core.time import Clock
from portalab.modules.marketplace import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.marketplace.activation.service import Activation
from portalab.modules.marketplace.eligibility.service import Eligibility
from portalab.modules.marketplace.entitlements.reader import Entitlements, ThemeEntitlementsReader
from portalab.modules.marketplace.events import register_event_types
from portalab.modules.marketplace.funding.service import Fundings
from portalab.modules.marketplace.grants.service import Grants
from portalab.modules.marketplace.integrations import (
    FEATURED_WIDGET,
    FeaturedWidget,
    ProductSearchProvider,
    catalog_tool,
    cosmetics_section,
)
from portalab.modules.marketplace.models import Project, ProjectFunding
from portalab.modules.marketplace.notify import CATEGORIES, notify_funders
from portalab.modules.marketplace.observability import log, metrics
from portalab.modules.marketplace.privacy.participant import MarketplaceParticipant
from portalab.modules.marketplace.products.service import Catalog
from portalab.modules.marketplace.projects.service import Projects
from portalab.modules.marketplace.purchase.service import Purchases
from portalab.modules.marketplace.refunds.service import Refunds
from portalab.modules.marketplace.resolution.service import Resolution
from portalab.modules.marketplace.revocation.service import Revocations
from portalab.modules.marketplace.settings import SETTINGS, MarketplaceConfig
from portalab.modules.marketplace.types.registry import register_builtin_types

OWNER = "module:marketplace"
INSTANCE = "marketplace"


class MarketplaceModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        *,
        clock: Clock | None = None,
        event_types: EventTypeRegistry = default_event_types,
        observables: ObservableRegistry = default_observables,
        product_types: ProductTypeRegistry = default_product_types,
        widgets: WidgetRegistry = default_widgets,
        search: SearchRegistry = default_search,
        tools: AIToolRegistry = default_ai_tools,
        sections: SectionRegistry = default_sections,
        permissions: PermissionRegistry = default_permissions,
    ) -> None:
        self.database = database
        self.audit = audit
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.clock = clock
        self.event_types = event_types
        self.observables = observables
        self.config = MarketplaceConfig()
        config = lambda: self.config  # noqa: E731
        self.resolution = Resolution(database, events, capabilities, clock=clock)
        self.projects = Projects(database, events, audit, self.resolution, clock=clock)
        self.fundings = Fundings(database, events, capabilities, self.resolution, config, clock=clock)
        self.product_types = product_types
        self.widgets = widgets
        self.search = search
        self.tools = tools
        self.sections = sections
        self.permissions = permissions
        self.catalog = Catalog(database, events, audit, product_types, config, clock=clock)
        self.eligibility = Eligibility(capabilities)
        self.activation = Activation(database, events, product_types, config, clock=clock)
        self.purchases = Purchases(
            database, events, capabilities, self.eligibility, self.activation, self.resolution, clock=clock
        )
        self.refunds = Refunds(
            database, events, audit, product_types, self.activation, self.resolution, clock=clock
        )
        self.grants = Grants(database, events, audit, self.activation, clock=clock)
        self.revocations = Revocations(
            database, events, audit, capabilities, self.activation, self.refunds, clock=clock
        )
        self.entitlements = Entitlements(database)

    def register(self) -> None:
        register_event_types(self.event_types)
        if not self.capabilities.system_providers(LIFECYCLE):
            self.capabilities.provide(LIFECYCLE, self.projects, instance_ref=INSTANCE, owner=OWNER)
        if not self.capabilities.system_providers(ENTITLEMENTS):
            self.capabilities.provide(ENTITLEMENTS, self.entitlements, instance_ref=INSTANCE, owner=OWNER)
        if not self.capabilities.system_providers(THEME_ENTITLEMENTS):
            self.capabilities.provide(
                THEME_ENTITLEMENTS, ThemeEntitlementsReader(self.database), instance_ref=INSTANCE, owner=OWNER
            )
        register_builtin_types(
            self.product_types, self.capabilities, self.widgets, self.permissions, lambda: self.config
        )
        if self.search.provider("product") is None:
            self.search.register(ProductSearchProvider(self.catalog, self.authorizer), owner=OWNER)
        if self.widgets.get(FEATURED_WIDGET.key) is None:
            self.widgets.register(FEATURED_WIDGET, FeaturedWidget(self.catalog, self.clock), owner=OWNER)
        if self.tools.get("marketplace.catalog") is None:
            self.tools.register(catalog_tool(self.catalog, self.clock))
        if self.sections.get("cosmetics") is None:
            self.sections.register(cosmetics_section(self.entitlements))
        participant = MarketplaceParticipant(self.database, clock=self.clock)
        for capability in (ERASURE_CAPABILITY, EXPORT_CAPABILITY):
            if not any(p.instance_ref == INSTANCE for p in self.capabilities.system_providers(capability)):
                self.capabilities.provide(capability, participant, instance_ref=INSTANCE, owner=OWNER)
        for key, label in CATEGORIES.items():
            if default_categories.get(key) is None:
                declare_category(key, OWNER, label, default_channels=("portal", "email"))
        # fundings are kept with the ledger they reference (integrity); erasure anonymizes them (R6)
        self.observables.declare(
            ObservedComponent(
                "marketplace",
                OWNER,
                label="Marketplace",
                functional_checks=(Check("funding_reconciliation", self.probe),),
                metrics=(
                    "marketplace.purchases",
                    "marketplace.refunds",
                    "marketplace.activation.activation_failed",
                    "marketplace.funding.added",
                    "marketplace.funding.released",
                    "marketplace.funding.consumed",
                ),
            )
        )

    def register_jobs(self, jobs: JobRegistry) -> list[Any]:
        async def reconcile() -> None:
            report = await self.resolution.reconcile()
            if report["drift"]:
                log.warning("funding reconciliation drift", extra={"fields": report})

        async def activations() -> None:
            await self.activation.retry()

        async def expiries() -> None:
            await self.revocations.expire()

        return [
            self.start,
            register_periodic(
                jobs, self.database, "marketplace.reconcile", timedelta(hours=1), reconcile, owner=OWNER
            ),
            register_periodic(
                jobs,
                self.database,
                "marketplace.activation_retry",
                timedelta(minutes=5),
                activations,
                owner=OWNER,
            ),
            register_periodic(
                jobs, self.database, "marketplace.grant_expiry", timedelta(minutes=15), expiries, owner=OWNER
            ),
        ]

    async def start(self) -> None:
        await self.refresh_config()

    async def refresh_config(self) -> None:
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                values = {
                    name: (await providers[0].provider.get(key)).value for name, key in SETTINGS.items()
                }
                self.config = replace(self.config, **values)
        except Exception:
            log.warning("marketplace configuration not refreshed")

    async def transition(
        self,
        actor: Principal,
        project_id: UUID,
        target: str,
        *,
        reason: str | None = None,
        note: str | None = None,
        expected_version: int | None = None,
        rules: dict[str, Any] | None = None,
    ) -> Project:
        """A transition, then (after commit) the funders' notification."""
        project = await self.projects.transition(
            actor,
            project_id,
            target,
            reason=reason,
            note=note,
            expected_version=expected_version,
            rules=rules,
        )
        async with self.database.session() as session:
            funders = list(
                (
                    await session.execute(
                        select(ProjectFunding.user_id)
                        .where(ProjectFunding.project_id == project.id)
                        .where(ProjectFunding.status != "destroyed_on_deletion")
                        .distinct()
                    )
                ).scalars()
            )
        seq = len(await self.projects.history(project.id))
        await notify_funders(self.capabilities, project.id, project.title, project.state, seq, funders)
        return project

    async def probe(self) -> CheckResult:
        try:
            report = await self.resolution.reconcile()
        except Exception:
            return CheckResult("degraded", "the economy is not reachable", {})
        facts = {**report, **{k: int(v) for k, v in metrics.snapshot().items()}}
        if report["drift"]:
            return CheckResult("degraded", "fundings and reservations disagree", facts)
        return CheckResult("ok", "fundings match their reservations", facts)
