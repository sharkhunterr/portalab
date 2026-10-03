"""Auto-suspension (T027; R12): ≥ ``automations.suspendAfterFailures`` consecutive failures, or a failure
share above ``automations.suspendFailureRate`` over the last 20 runs, suspends the automation with a reason,
an ``automation.suspended`` event and an ``automations.suspended`` notification to automation managers.
Only an explicit re-enable resumes it (counters reset)."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, WithPermission
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.authz_port import Principal
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.automations.models import Automation, Execution
from portalab.modules.automations.observability import log, metrics
from portalab.modules.automations.permissions import MANAGE

FAILURES = ("failed", "timeout")
COUNTED = ("success", "failed", "timeout", "refused")


class Suspender:
    def __init__(
        self,
        events: EventPublisher,
        capabilities: CapabilityRegistry,
        config: Any,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.events = events
        self.capabilities = capabilities
        self.config = config
        self.clock = clock

    async def record(self, session: AsyncSession, automation: Automation, status: str) -> bool:
        """Accounts one finished execution; True when the automation was just suspended."""
        if status in FAILURES:
            automation.consecutive_failures += 1
        elif status in ("success", "no_op"):
            automation.consecutive_failures = 0
        if automation.state != "active":
            return False
        config = self.config()
        reason = None
        if automation.consecutive_failures >= config.suspend_after_failures:
            reason = f"{automation.consecutive_failures} consecutive failures"
        else:
            recent = list(
                (
                    await session.execute(
                        select(Execution.status)
                        .where(Execution.automation_id == automation.id, Execution.status.in_(COUNTED))
                        .order_by(Execution.started_at.desc())
                        .limit(20)
                    )
                ).scalars()
            )
            failed = sum(1 for s in recent if s in FAILURES)
            if len(recent) >= 20 and failed / len(recent) > config.suspend_failure_rate:
                reason = f"{failed} failures in the last {len(recent)} runs"
        if reason is None:
            return False
        automation.state, automation.suspend_reason = "suspended", reason
        await self.events.publish(
            session,
            "automation.suspended",
            {"automation": automation.key, "reason": reason},
            occurred_at=utc_now(self.clock),
            actor=Principal(channel="system"),
            subject=SubjectRef("automation", str(automation.id)),
            dedup_key=f"automation.suspended:{automation.id}:{automation.updated_at.isoformat()}",
        )
        metrics.increment("automations.suspended")
        return True

    async def notify(self, automation: Automation) -> None:
        try:
            providers = self.capabilities.system_providers(NOTIFY)
            if providers:
                await providers[0].provider.send(
                    CommunicationRequest(
                        category="automations.suspended",
                        template_key="automations:notify.suspended",
                        audience=WithPermission(MANAGE),
                        dedup_key=f"automation-suspended:{automation.id}:{automation.updated_at.isoformat()}",
                        kind="alert",
                        priority="high",
                        params={"automation": automation.name, "reason": automation.suspend_reason or ""},
                        source="module",
                        action_url=f"/admin/automations/{automation.id}",
                    )
                )
        except Exception:
            log.warning("suspension notification not sent")
