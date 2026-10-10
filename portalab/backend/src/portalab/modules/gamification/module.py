"""Gamification module facade (spec 013, Slice A): ledger, economy service, versioned reward rules applied to
events, modifiers, anti-abuse with anomaly review, levels, achievements, manual/automation/contribution
grants, Coins destruction at deletion and progression read APIs."""

from dataclasses import replace
from datetime import timedelta
from typing import Any

from sqlalchemy import delete

from portalab.capabilities.ai import AIToolRegistry, default_ai_tools
from portalab.capabilities.automation_actions import ActionRegistry, default_actions
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.dashboard import WidgetRegistry, default_widgets
from portalab.capabilities.economy import CATALOG, ECONOMY, LEADERBOARDS, MODIFIERS, REWARDS
from portalab.capabilities.events import (
    ConsumerRegistry,
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
from portalab.capabilities.statistics import PROGRESSION
from portalab.capabilities.support import CONTRIBUTIONS
from portalab.capabilities.visibility import PREFERENCE_CAPABILITY
from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Authorizer
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.time import Clock, utc_now
from portalab.core.visibility_port import OwnerOnlyVisibility, VisibilityFilter
from portalab.modules.gamification import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.gamification.achievements.evaluator import Achievements
from portalab.modules.gamification.anomaly.service import AnomalyService
from portalab.modules.gamification.antiabuse.guards import Guards
from portalab.modules.gamification.consumers.reward import CONSUMER, RewardPipeline
from portalab.modules.gamification.economy.service import EconomyServiceImpl
from portalab.modules.gamification.events import register_event_types
from portalab.modules.gamification.integrations import (
    DAILY_WIDGET,
    PROGRESS_WIDGET,
    CatalogFacade,
    DailyObjectivesWidget,
    ProgressionPreferences,
    ProgressWidget,
    register_actions,
    register_tools,
)
from portalab.modules.gamification.integrations import (
    PROGRESSION as PROGRESSION_DATUM,
)
from portalab.modules.gamification.leaderboards.service import LeaderboardService
from portalab.modules.gamification.ledger.writer import LedgerWriter
from portalab.modules.gamification.levels.service import LevelService
from portalab.modules.gamification.manual.service import RewardServiceImpl
from portalab.modules.gamification.models import AppliedEvent, Withheld
from portalab.modules.gamification.modifiers.combiner import ModifierCombiner
from portalab.modules.gamification.notify import CATEGORIES, Notifier
from portalab.modules.gamification.observability import log
from portalab.modules.gamification.privacy.participant import GamificationParticipant
from portalab.modules.gamification.progression.service import ProgressionService
from portalab.modules.gamification.progression.summary import ProgressionChanges
from portalab.modules.gamification.quests.service import Quests
from portalab.modules.gamification.rules.store import RuleStore
from portalab.modules.gamification.settings import SETTINGS, EconomyConfig
from portalab.modules.gamification.streaks.level_rewards import CONSUMER as LEVEL_REWARDS
from portalab.modules.gamification.streaks.level_rewards import LevelRewards
from portalab.modules.gamification.streaks.service import Pace, Streaks
from portalab.modules.gamification.verify.verifier import verify

OWNER = "module:gamification"
INSTANCE = "gamification"
STREAK_INSTANCE = "streak"
PACE_INSTANCE = "pace"
PURGE_JOB = "gamification.purge"
LEADERBOARD_JOB = "gamification.leaderboards"  # snapshots older than refreshMinutes are rebuilt


class GamificationModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        *,
        clock: Clock | None = None,
        visibility: VisibilityFilter | None = None,
        event_types: EventTypeRegistry = default_event_types,
        consumers: ConsumerRegistry = default_consumers,
        widgets: WidgetRegistry = default_widgets,
        observables: ObservableRegistry = default_observables,
        actions: ActionRegistry = default_actions,
        tools: AIToolRegistry = default_ai_tools,
    ) -> None:
        self.database = database
        self.events = events
        self.audit = audit
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.clock = clock
        self.visibility = visibility or OwnerOnlyVisibility()
        self.event_types = event_types
        self.consumers = consumers
        self.widgets = widgets
        self.observables = observables
        self.actions = actions
        self.tools = tools
        self.config = EconomyConfig()
        config = lambda: self.config  # noqa: E731
        self.levels = LevelService(database, lambda: self.config.level_curve_active, clock=clock)
        self.writer = LedgerWriter(events, self.levels, clock=clock)
        self.economy = EconomyServiceImpl(database, self.writer, clock=clock)
        self.rules = RuleStore(database, audit, events, event_types, clock=clock)
        self.combiner = ModifierCombiner(capabilities)
        self.guards = Guards(config)
        self.anomalies = AnomalyService(
            database, self.writer, events, audit, capabilities, config, clock=clock
        )
        self.achievements = Achievements(database, self.writer, events, audit, capabilities, clock=clock)
        self.notifier = Notifier(capabilities)
        self.pipeline = RewardPipeline(
            database,
            self.writer,
            self.rules,
            self.combiner,
            self.guards,
            self.anomalies,
            self.achievements,
            self.notifier,
            config,
            clock=clock,
        )
        self.rewards = RewardServiceImpl(
            database,
            self.writer,
            self.guards,
            self.anomalies,
            self.achievements,
            self.notifier,
            audit,
            authorizer,
            config,
            clock=clock,
        )
        self.quests = Quests(database, self.writer, events, audit, capabilities, config, clock=clock)
        self.pipeline.quests = self.quests
        self.progression = ProgressionService(database, self.levels, self.achievements.unlock_shares)
        self.streaks = Streaks(database, config)
        self.pace = Pace(config)
        self.level_rewards = LevelRewards(database, self.writer, capabilities, config)
        self.leaderboards = LeaderboardService(
            database, self.levels, self.visibility, capabilities, config, clock=clock
        )

    def register(self) -> None:
        register_event_types(self.event_types)
        if self.consumers.get(CONSUMER) is None:
            self.consumers.register(self.pipeline.consumer())
        if self.consumers.get(LEVEL_REWARDS) is None:
            self.consumers.register(self.level_rewards.consumer())
        for instance, modifier in ((STREAK_INSTANCE, self.streaks), (PACE_INSTANCE, self.pace)):
            if not any(p.instance_ref == instance for p in self.capabilities.system_providers(MODIFIERS)):
                self.capabilities.provide(MODIFIERS, modifier, instance_ref=instance, owner=OWNER)
        for name, provider in (
            (ECONOMY, self.economy),
            (REWARDS, self.rewards),
            (PROGRESSION, self.progression),
            (CONTRIBUTIONS, self.rewards),
            (LEADERBOARDS, self.leaderboards),
            (CATALOG, CatalogFacade(self.achievements, self.progression, self.quests)),
        ):
            if not self.capabilities.system_providers(name):
                self.capabilities.provide(name, provider, instance_ref=INSTANCE, owner=OWNER)
        participant = GamificationParticipant(
            self.database, self.writer, clock=self.clock, leaderboards=self.leaderboards
        )
        for capability in (ERASURE_CAPABILITY, EXPORT_CAPABILITY):
            if not any(p.instance_ref == INSTANCE for p in self.capabilities.system_providers(capability)):
                self.capabilities.provide(capability, participant, instance_ref=INSTANCE, owner=OWNER)
        if not any(
            p.instance_ref == INSTANCE for p in self.capabilities.system_providers(PREFERENCE_CAPABILITY)
        ):
            self.capabilities.provide(
                PREFERENCE_CAPABILITY,
                ProgressionPreferences(self.database, clock=self.clock),
                instance_ref=INSTANCE,
                owner=OWNER,
                metadata={"datum_classes": [PROGRESSION_DATUM]},
            )
        for category in CATEGORIES:
            if default_categories.get(category) is None:
                declare_category(category, OWNER, f"gamification:category.{category.split('.', 1)[1]}")
        default_retention_targets.register(
            RetentionTarget(
                "gamification.withheld",
                "gamification.withheld",
                "activity",
                "occurred_at",
                "delete",
                OWNER,
                window=lambda: timedelta(days=max(1, self.config.withheld_retention_days)),
            )
        )
        if self.widgets.get(PROGRESS_WIDGET.key) is None:
            self.widgets.register(PROGRESS_WIDGET, ProgressWidget(self.progression, self.clock), owner=OWNER)
        if self.widgets.get(DAILY_WIDGET.key) is None:
            self.widgets.register(DAILY_WIDGET, DailyObjectivesWidget(self.quests, self.clock), owner=OWNER)
        if not any(p.kind == "progression" for p in self.widgets.summaries()):  # 027: since last visit
            self.widgets.register_summary(ProgressionChanges(self.database, self.progression), owner=OWNER)
        register_tools(self.tools, self.progression, self.clock)
        register_actions(self.rewards, self.actions)
        self.observables.declare(
            ObservedComponent(
                "gamification",
                OWNER,
                label="Gamification",
                functional_checks=(Check("ledger", self.probe),),
                metrics=("gamification.ledger.drift", "gamification.withheld.anomaly"),
            )
        )

    def register_jobs(self, jobs: JobRegistry) -> list[Any]:
        async def purge() -> None:
            await self.purge()

        async def leaderboards() -> None:
            await self.leaderboards.refresh()

        return [
            self.start,
            register_periodic(jobs, self.database, PURGE_JOB, timedelta(hours=6), purge, owner=OWNER),
            register_periodic(
                jobs, self.database, LEADERBOARD_JOB, timedelta(minutes=5), leaderboards, owner=OWNER
            ),
        ]

    async def start(self) -> None:
        await self.refresh_config()
        await self.levels.ensure_default()
        await self.quests.ensure_discovery()  # 027: a new member's first steps

    async def refresh_config(self) -> None:
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                values = {
                    name: (await providers[0].provider.get(key)).value for name, key in SETTINGS.items()
                }
                self.config = replace(self.config, **values)
        except Exception:
            log.warning("gamification configuration not refreshed")

    async def purge(self) -> int:
        """Reviewed withheld entries and old applied-event markers expire (retention)."""
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            withheld = await uow.session.execute(
                delete(Withheld).where(
                    Withheld.status != "flagged",
                    Withheld.occurred_at < now - timedelta(days=max(1, self.config.withheld_retention_days)),
                )
            )
            applied = await uow.session.execute(
                delete(AppliedEvent).where(AppliedEvent.applied_at < now - timedelta(days=180))
            )
        return int(getattr(withheld, "rowcount", 0) or 0) + int(getattr(applied, "rowcount", 0) or 0)

    async def probe(self) -> CheckResult:
        report = await verify(self.database)
        facts = {"balances": report.checked, "drift": len(report.drifts)}
        if report.drifts:
            return CheckResult("degraded", "ledger and balances disagree", facts)
        return CheckResult("ok", "ledger consistent", facts)
