"""Alerts (T027; FR-020/022): raised for important conditions (component down/failing, critical anomaly)
through the ``notifications.send_alert`` port (010; skipped while absent) and always published as
``observability.alert_raised`` so Automations (019) can trigger on them. No delivery channel here."""

from datetime import datetime
from typing import Any

from portalab.capabilities.observability import SEND_ALERT, Alert
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.observability.observability import log, metrics


class AlertService:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.capabilities = capabilities
        self.clock = clock

    async def raise_alert(
        self,
        key: str,
        title: str,
        severity: str,
        component: str,
        facts: dict[str, Any] | None = None,
        *,
        at: datetime | None = None,
    ) -> Alert:
        alert = Alert(key, title, severity, component, at or utc_now(self.clock), dict(facts or {}))  # type: ignore[arg-type]
        async with self.database.unit_of_work() as uow:
            await self.events.publish(
                uow.session,
                "observability.alert_raised",
                {"alert": key, "severity": severity, "component": component, "title": title[:200]},
                occurred_at=alert.raised_at,
                subject=SubjectRef("component", component),
                source="observability",
            )
        providers = self.capabilities.system_providers(SEND_ALERT)
        if providers:
            try:
                await providers[0].provider.send_alert(alert)
            except Exception:
                log.warning("alert delivery failed", extra={"fields": {"alert": key}})
        metrics.increment("observability.alerts")
        return alert
