"""Automations module facade (spec 019): registries (owner actions, closed condition leaves, automatable
triggers), versioned definitions, the trigger consumer and scheduler, the Gate, Runner, approvals,
auto-suspension, history, dry-run and templates."""

from dataclasses import replace
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select

from portalab.capabilities.automation_actions import ActionRegistry, default_actions
from portalab.capabilities.automations import ConditionRegistry, default_conditions
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.events import (
    ConsumerRegistry,
    EventTypeRegistry,
    default_consumers,
    default_event_types,
)
from portalab.capabilities.notifications import declare_category, default_categories
from portalab.capabilities.observability import (
    AUTOMATION_STATUS,
    AutomationStatus,
    ObservableRegistry,
    default_observables,
)
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.retention import RetentionTarget, default_retention_targets
from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Authorizer
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.permissions import PermissionRegistry, default_permissions
from portalab.core.time import Clock, utc_now
from portalab.modules.automations import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.automations.actions import register_engine_actions
from portalab.modules.automations.approvals.service import Approvals
from portalab.modules.automations.definitions.service import Definitions
from portalab.modules.automations.evaluator.evaluator import Evaluator
from portalab.modules.automations.events import register_event_types
from portalab.modules.automations.gate.gate import Gate
from portalab.modules.automations.history.service import History
from portalab.modules.automations.identity.guard import IdentityGuard
from portalab.modules.automations.models import Automation, Execution
from portalab.modules.automations.observability import log
from portalab.modules.automations.registries.conditions import register_builtin
from portalab.modules.automations.runner.runner import Runner
from portalab.modules.automations.scheduler.scheduler import Scheduler
from portalab.modules.automations.settings import SETTINGS, AutomationsConfig
from portalab.modules.automations.suspender.suspender import Suspender
from portalab.modules.automations.triggers.consumer import CONSUMER, Triggers

OWNER = "module:automations"
CATEGORIES = {
    "automations.suspended": "automations:category.suspended",
    "automations.approval": "automations:category.approval",
    "automations.message": "automations:category.message",
}


class AutomationsModule:
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
        consumers: ConsumerRegistry = default_consumers,
        actions: ActionRegistry = default_actions,
        conditions: ConditionRegistry = default_conditions,
        permissions: PermissionRegistry = default_permissions,
        observables: ObservableRegistry = default_observables,
    ) -> None:
        self.database = database
        self.events = events
        self.audit = audit
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.clock = clock
        self.event_types = event_types
        self.consumers = consumers
        self.actions = actions
        self.conditions = conditions
        self.permissions = permissions
        self.observables = observables
        self.config = AutomationsConfig()
        config = lambda: self.config  # noqa: E731
        self.guard = IdentityGuard(authorizer, capabilities)
        self.evaluator = Evaluator(conditions)
        self.suspender = Suspender(events, capabilities, config, clock=clock)
        self.runner = Runner(
            database, actions, permissions, self.guard, self.evaluator, self.suspender, config, clock=clock
        )
        self.gate = Gate(config)
        self.triggers = Triggers(database, self.gate, self.runner, event_types, config, clock=clock)
        self.scheduler = Scheduler(database, self.triggers, clock=clock)
        self.approvals = Approvals(database, self.runner, audit, events, clock=clock)
        self.definitions = Definitions(
            database,
            audit,
            events,
            self.guard,
            types=event_types,
            actions=actions,
            conditions=conditions,
            permissions=permissions,
            config=config,
            on_change=self.triggers.invalidate,
            clock=clock,
        )
        self.history = History(database, clock=clock)

    def register(self) -> None:
        register_event_types(self.event_types)
        register_builtin(self.conditions, self.capabilities, self.authorizer)
        register_engine_actions(self.actions, self.database, self.events, clock=self.clock)
        if self.consumers.get(CONSUMER) is None:
            self.consumers.register(self.triggers.consumer())
        for key, label in CATEGORIES.items():
            if default_categories.get(key) is None:
                declare_category(
                    key,
                    OWNER,
                    label,
                    default_channels=("portal", "email") if key != "automations.message" else ("portal",),
                )
        default_retention_targets.register(
            RetentionTarget(
                "automations.executions",
                "automations.executions",
                "technical",
                "started_at",
                "delete",
                OWNER,
                window=lambda: timedelta(days=max(1, self.config.execution_retention_days)),
            )
        )
        if not self.capabilities.system_providers(AUTOMATION_STATUS):  # feeds Observability's component
            self.capabilities.provide(AUTOMATION_STATUS, self, instance_ref="automations", owner=OWNER)

    def register_jobs(self, jobs: JobRegistry) -> list[Any]:
        async def schedule() -> None:
            await self.scheduler.run()

        async def expire() -> None:
            await self.approvals.expire()

        async def purge() -> None:
            await self.history.purge(self.config.execution_retention_days)

        return [
            self.start,
            register_periodic(
                jobs, self.database, "automations.scheduler", timedelta(minutes=1), schedule, owner=OWNER
            ),
            register_periodic(
                jobs, self.database, "automations.approvals_expire", timedelta(minutes=5), expire, owner=OWNER
            ),
            register_periodic(
                jobs, self.database, "automations.purge", timedelta(hours=6), purge, owner=OWNER
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
            log.warning("automations configuration not refreshed")
        self.triggers.invalidate()

    async def status(self) -> AutomationStatus:
        """``automations.status`` (025): counts over the last day, suspended automations with their reason."""
        since = utc_now(self.clock) - timedelta(days=1)
        async with self.database.session() as session:
            executions = int(
                await session.scalar(
                    select(func.count()).select_from(Execution).where(Execution.started_at >= since)
                )
                or 0
            )
            failures = int(
                await session.scalar(
                    select(func.count())
                    .select_from(Execution)
                    .where(Execution.started_at >= since, Execution.status.in_(("failed", "timeout")))
                )
                or 0
            )
            suspended = (
                await session.execute(
                    select(Automation.id, Automation.suspend_reason).where(Automation.state == "suspended")
                )
            ).all()
        return AutomationStatus(
            await self.definitions.count_active(),
            executions,
            failures,
            tuple({"rule_id": str(i), "reason": reason or ""} for i, reason in suspended),
        )
