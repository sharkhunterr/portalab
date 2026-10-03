"""Statistics module facade (spec 017)."""

from dataclasses import replace
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.config import I18N_POLICY_READER
from portalab.capabilities.dashboard import WidgetRegistry, default_widgets
from portalab.capabilities.events import (
    STATS_CAPABILITY,
    Consumer,
    ConsumerContext,
    ConsumerRegistry,
    Envelope,
    EventTypeRegistry,
    default_consumers,
    default_event_types,
)
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
from portalab.capabilities.retention import RetentionTarget, default_retention_targets
from portalab.capabilities.statistics import PROVIDER, PackRegistry, default_packs
from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.time import Clock, utc_now
from portalab.core.visibility_port import VisibilityFilter
from portalab.modules.statistics import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.statistics.definitions.service import DefinitionService
from portalab.modules.statistics.events import register_event_types
from portalab.modules.statistics.models import DefinitionStatus, ProjectionState
from portalab.modules.statistics.observability import log
from portalab.modules.statistics.packs.registry import register_builtin
from portalab.modules.statistics.participant import StatisticsParticipant
from portalab.modules.statistics.privacy.guard import PrivacyGuard
from portalab.modules.statistics.projection.consumers import Projection, sync_consumers
from portalab.modules.statistics.provider.provider import Provider
from portalab.modules.statistics.settings import SETTINGS, StatisticsConfig
from portalab.modules.statistics.unlock.evaluator import UnlockEvaluator
from portalab.modules.statistics.widgets import CARD, StatisticCard
from portalab.modules.statistics.wrapped.service import WrappedService

OWNER = "module:statistics"
REFRESH_CONSUMER = "statistics.definitions"
WRAPPED_JOB = "statistics.wrapped_generate"


class StatisticsModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        *,
        salt: bytes,
        visibility: VisibilityFilter | None = None,
        clock: Clock | None = None,
        event_types: EventTypeRegistry = default_event_types,
        consumers: ConsumerRegistry = default_consumers,
        packs: PackRegistry = default_packs,
        widgets: WidgetRegistry = default_widgets,
        observables: ObservableRegistry = default_observables,
    ) -> None:
        self.database = database
        self.events = events
        self.audit = audit
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.clock = clock
        self.config = StatisticsConfig()
        self.default_timezone = "UTC"
        self.event_types = event_types
        self.consumers = consumers
        self.packs = packs
        self.widgets = widgets
        self.observables = observables
        self.definitions = DefinitionService(
            database, events, audit, event_types, lambda: self.config, head_seq=self.head_seq, clock=clock
        )
        self.projection = Projection(database, salt, self.timezone)
        self.unlocks = UnlockEvaluator(database, events, capabilities, clock=clock)
        self.guard = PrivacyGuard(visibility)
        self.provider = Provider(
            database,
            self.definitions,
            self.unlocks,
            self.guard,
            authorizer,
            capabilities,
            lambda: self.config,
            self.timezone,
            clock=clock,
        )
        self.wrapped = WrappedService(
            database, events, capabilities, self.provider, self.timezone, clock=clock
        )

    def timezone(self) -> str:
        return self.config.timezone or self.default_timezone

    async def head_seq(self) -> int:
        try:
            providers = self.capabilities.system_providers(STATS_CAPABILITY)
            if providers:
                return int((await providers[0].provider.snapshot()).head_seq)
        except Exception:
            log.warning("event head unavailable; forward-only bound set to 0")
        return 0

    def register(self) -> None:
        register_event_types(self.event_types)
        if default_categories.get("statistics.wrapped") is None:
            declare_category(
                "statistics.wrapped",
                OWNER,
                "statistics:category.wrapped",
                default_channels=("portal", "email"),
            )
        if not self.packs.packs() or not any(owner == OWNER for owner, *_ in self.packs.packs()):
            register_builtin(self.packs)
        if not self.capabilities.system_providers(PROVIDER):
            self.capabilities.provide(PROVIDER, self.provider, instance_ref="statistics", owner=OWNER)
        if self.widgets.get(CARD.key) is None:
            self.widgets.register(CARD, StatisticCard(self.provider), owner=OWNER)
        participant = StatisticsParticipant(self.database)
        for capability in (ERASURE_CAPABILITY, EXPORT_CAPABILITY):
            if not any(
                p.instance_ref == "statistics" for p in self.capabilities.system_providers(capability)
            ):
                self.capabilities.provide(capability, participant, instance_ref="statistics", owner=OWNER)
        months = lambda: timedelta(days=31 * max(1, self.config.bucket_retention_months))  # noqa: E731
        for name, table, column in (
            ("statistics.buckets", "stats.buckets", "bucket_day"),
            ("statistics.members", "stats.members", "bucket_day"),
            ("statistics.applied_events", "stats.applied_events", "bucket_day"),
        ):
            default_retention_targets.register(
                RetentionTarget(name, table, "aggregate", column, "delete", OWNER, window=months)
            )
        if self.consumers.get(REFRESH_CONSUMER) is None:
            self.consumers.register(
                Consumer(
                    REFRESH_CONSUMER,
                    frozenset({"statistics.definition_changed"}),
                    self._on_definition,
                    OWNER,
                    replay_safe=True,
                )
            )
        self.observables.declare(
            ObservedComponent(
                "statistics", OWNER, label="Statistics", functional_checks=(Check("freshness", self.probe),)
            )
        )

    def register_jobs(self, jobs: JobRegistry) -> list[Any]:
        async def generate() -> None:
            if self.config.wrapped_enabled:
                await self.wrapped.generate()

        return [
            self.start,
            register_periodic(jobs, self.database, WRAPPED_JOB, timedelta(days=1), generate, owner=OWNER),
        ]

    async def _on_definition(self, envelope: Envelope, ctx: ConsumerContext) -> None:
        await self.sync()

    async def refresh_config(self) -> None:
        try:
            reader = self.capabilities.system_providers(CONFIG)
            if reader:
                values = {name: (await reader[0].provider.get(key)).value for name, key in SETTINGS.items()}
                self.config = replace(self.config, **values)
            policy = self.capabilities.system_providers(I18N_POLICY_READER)
            if policy:
                self.default_timezone = (await policy[0].provider.get()).default_time_zone or "UTC"
        except Exception:
            log.warning("statistics configuration not refreshed")

    async def install_packs(self) -> int:
        """Store the definitions of the active packs; built-in ones are activated the first time they appear
        (plugin packs stay inactive until the Admin enables them)."""
        installed = 0
        for definition, owner, active in self.packs.definitions():
            async with self.database.session() as session:
                known = await session.get(DefinitionStatus, definition.key)
            try:
                version = await self.definitions.save(
                    None, definition, source="builtin" if owner == OWNER else owner
                )
                if known is None and active:
                    await self.definitions.activate(None, definition.key, version)
                installed += 1
            except Exception:
                log.warning("statistic pack definition skipped", extra={"stat": definition.key})
        return installed

    async def start(self) -> None:
        await self.refresh_config()
        await self.install_packs()
        await self.sync()

    async def sync(self) -> int:
        return sync_consumers(
            self.consumers, self.projection, await self.definitions.versions_in_projection()
        )

    async def activate(self, actor: Principal, key: str, version: int | None = None) -> int:
        version = await self.definitions.activate(actor, key, version)
        await self.sync()
        return version

    async def status(self) -> dict[str, Any]:
        lag: dict[str, int] = {}
        try:
            providers = self.capabilities.system_providers(STATS_CAPABILITY)
            if providers:
                snapshot = await providers[0].provider.snapshot()
                lag = {k: v for k, v in snapshot.lag_by_consumer.items() if k.startswith("statistics.")}
        except Exception:
            lag = {}
        async with self.database.session() as session:
            states = (
                (await session.execute(select(ProjectionState).order_by(ProjectionState.stat_key)))
                .scalars()
                .all()
            )
        return {
            "timezone": self.timezone(),
            "lag": lag,
            "projections": [
                {
                    "stat_key": s.stat_key,
                    "version": s.def_version,
                    "events": s.events,
                    "last_event_at": s.last_event_at.isoformat() if s.last_event_at else None,
                    "updated_at": s.updated_at.isoformat(),
                }
                for s in states
            ],
        }

    async def probe(self) -> CheckResult:
        async with self.database.session() as session:
            active = int(
                await session.scalar(
                    select(func.count())
                    .select_from(DefinitionStatus)
                    .where(DefinitionStatus.status == "active")
                )
                or 0
            )
        status = await self.status()
        behind = sum(1 for v in status["lag"].values() if v > 1000)
        facts = {
            "active_definitions": active,
            "lagging": behind,
            "checked_at": utc_now(self.clock).isoformat(),
        }
        if behind:
            return CheckResult("degraded", f"{behind} statistic projection(s) behind", facts)
        return CheckResult("ok", "statistics are fresh", facts)
