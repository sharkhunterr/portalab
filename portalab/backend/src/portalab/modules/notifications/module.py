"""Notifications module facade (spec 010)."""

from dataclasses import replace
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.automation_actions import ActionRegistry, default_actions
from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.capabilities.events import (
    ConsumerRegistry,
    EventTypeRegistry,
    default_consumers,
    default_event_types,
)
from portalab.capabilities.identity_directory import VERIFICATION_CHANNEL
from portalab.capabilities.notifications import (
    NOTIFY,
    CategoryRegistry,
    CommunicationRef,
    CommunicationRequest,
    EmailTransport,
    WithPermission,
    declare_category,
    default_categories,
)
from portalab.capabilities.observability import (
    SEND_ALERT,
    Alert,
    Check,
    CheckResult,
    ObservableRegistry,
    ObservedComponent,
    default_observables,
)
from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY, EXPORT_CAPABILITY
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.retention import RetentionTarget, default_retention_targets
from portalab.core.audit_port import AuditSink
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.jobs.periodic import register_periodic
from portalab.core.jobs.registry import JobRegistry
from portalab.core.time import Clock, utc_now
from portalab.modules.notifications import permissions as _permissions  # noqa: F401 — declares permissions
from portalab.modules.notifications.automation import register_action
from portalab.modules.notifications.channels.email import EMAIL_JOB, EmailChannel, EmailVerificationChannel
from portalab.modules.notifications.events import register_event_types
from portalab.modules.notifications.fanout.service import FanOut
from portalab.modules.notifications.maintenance.reminders import JOB as REMINDER_JOB
from portalab.modules.notifications.maintenance.reminders import MaintenanceReminders
from portalab.modules.notifications.models import Category, Delivery
from portalab.modules.notifications.observability import log, metrics
from portalab.modules.notifications.participant import NotificationsParticipant
from portalab.modules.notifications.producer.service import Producer
from portalab.modules.notifications.settings import SETTINGS, NotificationsConfig
from portalab.modules.notifications.sources.sources import sources_consumer

OWNER = "module:notifications"
DIGEST_JOB = "notifications.digest"

BUILTIN = (
    ("system.maintenance", "notifications:category.maintenance", "high", ("portal", "email"), (), True),
    ("system.health", "notifications:category.health", "critical", ("portal",), (), True),
    ("account.security", "notifications:category.security", "high", ("portal", "email"), ("portal",), False),
    ("communications.broadcast", "notifications:category.broadcast", "normal", ("portal",), (), True),
)


class AlertPort:
    """025's ``notifications.send_alert``: operational alerts reach holders of ``observability.read``."""

    def __init__(self, module: "NotificationsModule") -> None:
        self.module = module

    async def send_alert(self, alert: Alert) -> None:
        # 027: readable alerts — the service by its name, a message per kind, a link to where it is fixed
        kind = str(alert.facts.get("kind") or "")
        template, url = {
            "connector": ("notifications:observability.service", "/admin/services"),
            "sync": ("notifications:observability.sync", "/admin/services"),
        }.get(kind, ("notifications:observability.alert", "/admin/observability"))
        label = str(alert.facts.get("label") or alert.component)[:120]
        await self.module.send(
            CommunicationRequest(
                category="system.health",
                template_key=template,
                audience=WithPermission("observability.read"),
                dedup_key=f"alert:{alert.key}:{alert.raised_at.isoformat()}",
                kind="alert",
                priority="critical" if alert.severity == "critical" else "high",
                params={
                    "title": alert.title[:200],
                    "component": label,
                    "name": label,
                    "status": str(alert.facts.get("status") or "degraded"),
                },
                source="system",
                subject_ref=f"alert:{alert.component}",
                required_permission="observability.read",
                action_url=url,
            )
        )


class NotificationsModule:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        authorizer: Authorizer,
        *,
        clock: Clock | None = None,
        categories: CategoryRegistry = default_categories,
        event_types: EventTypeRegistry = default_event_types,
        consumers: ConsumerRegistry = default_consumers,
        observables: ObservableRegistry = default_observables,
        actions: ActionRegistry = default_actions,
        transport: EmailTransport | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.audit = audit
        self.capabilities = capabilities
        self.authorizer = authorizer
        self.clock = clock
        self.config = NotificationsConfig()
        self.categories = categories
        self.event_types = event_types
        self.consumers = consumers
        self.observables = observables
        self.actions = actions
        self.fanout = FanOut(database, authorizer, capabilities, categories, lambda: self.config, clock=clock)
        self.producer = Producer(
            database, events, authorizer, capabilities, categories, self.fanout, clock=clock
        )
        self.email = EmailChannel(
            database, events, capabilities, lambda: self.config, transport=transport, clock=clock
        )
        self.reminders = MaintenanceReminders(database, lambda request: self.send(request), clock=clock)

    async def send(
        self, request: CommunicationRequest, *, caller: Principal | None = None
    ) -> CommunicationRef:
        return await self.producer.send(request, caller=caller)

    def register(self) -> None:
        for key, label, priority, channels, mandatory, mutable in BUILTIN:
            if self.categories.get(key) is None:
                declare_category(
                    key,
                    OWNER,
                    label,
                    default_priority=priority,  # type: ignore[arg-type]
                    default_channels=channels,
                    mandatory_channels=mandatory,
                    user_mutable=mutable,
                    registry=self.categories,
                )
        register_event_types(self.event_types)
        for name, provider, ref in (
            (NOTIFY, self, "notifications"),
            (SEND_ALERT, AlertPort(self), "notifications"),
            (VERIFICATION_CHANNEL, EmailVerificationChannel(self.email), "notifications.email"),
        ):
            if not self.capabilities.system_providers(name):
                self.capabilities.provide(name, provider, instance_ref=ref, owner=OWNER)
        participant = NotificationsParticipant(self.database)
        for capability in (ERASURE_CAPABILITY, EXPORT_CAPABILITY):
            if not any(
                p.instance_ref == "notifications" for p in self.capabilities.system_providers(capability)
            ):
                self.capabilities.provide(capability, participant, instance_ref="notifications", owner=OWNER)
        window = lambda: timedelta(days=max(1, self.config.retention_days))  # noqa: E731
        for name, table, column in (
            ("notifications.items", "notify.notifications", "created_at"),
            ("notifications.deliveries", "notify.deliveries", "created_at"),
        ):
            default_retention_targets.register(
                RetentionTarget(name, table, "activity", column, "delete", OWNER, window=window)
            )
        for consumer in (self.reminders.consumer(), sources_consumer(lambda request: self.send(request))):
            if self.consumers.get(consumer.name) is None:
                self.consumers.register(consumer)
        register_action(lambda request, principal: self.send(request, caller=principal), self.actions)
        self.observables.declare(
            ObservedComponent(
                "notifications",
                OWNER,
                label="Notifications",
                functional_checks=(Check("delivery", self.probe),),
            )
        )

    def register_jobs(self, jobs: JobRegistry) -> list[Any]:
        jobs.register(
            EMAIL_JOB, self.email.run, idempotency="delivery status checked before sending", owner=OWNER
        )

        async def reminder(payload: dict[str, Any]) -> None:
            await self.reminders.run(payload)

        jobs.register(
            REMINDER_JOB,
            reminder,
            idempotency="reminder status checked; communications deduplicated",
            owner=OWNER,
        )

        async def digest() -> None:
            await self.email.digest()

        return [
            self.start,
            register_periodic(jobs, self.database, DIGEST_JOB, timedelta(hours=1), digest, owner=OWNER),
        ]

    async def refresh_config(self) -> None:
        try:
            providers = self.capabilities.system_providers(CONFIG)
            if providers:
                values = {
                    name: (await providers[0].provider.get(key)).value for name, key in SETTINGS.items()
                }
                self.config = replace(self.config, **values)
        except Exception:
            log.warning("notification configuration not refreshed")

    async def start(self) -> None:
        await self.refresh_config()
        await self.mirror_categories()

    async def mirror_categories(self) -> None:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            for category in self.categories.all():
                values = {
                    "owner": category.owner,
                    "label_key": category.label_key,
                    "default_priority": category.default_priority,
                    "default_channels": list(category.default_channels),
                    "mandatory_channels": list(category.mandatory_channels),
                    "user_mutable": category.user_mutable,
                    "status": "active",
                    "updated_at": now,
                }
                await uow.session.execute(
                    insert(Category)
                    .values(key=category.key, **values)
                    .on_conflict_do_update(index_elements=["key"], set_=values)
                )

    async def status(self) -> dict[str, Any]:
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(
                        Delivery.channel, Delivery.status, Delivery.suppress_reason, func.count()
                    ).group_by(Delivery.channel, Delivery.status, Delivery.suppress_reason)
                )
            ).all()
        return {
            "email_enabled": self.config.email_enabled,
            "deliveries": [
                {"channel": channel, "status": status, "reason": reason, "count": int(count)}
                for channel, status, reason, count in rows
            ],
            "metrics": metrics.snapshot(),
        }

    async def probe(self) -> CheckResult:
        status = await self.status()
        failed = sum(d["count"] for d in status["deliveries"] if d["status"] == "failed")
        facts = {"failed_deliveries": failed, "email_enabled": self.config.email_enabled}
        if failed:
            return CheckResult("degraded", f"{failed} delivery(ies) failed", facts)
        return CheckResult("ok", "notifications are delivered", facts)
