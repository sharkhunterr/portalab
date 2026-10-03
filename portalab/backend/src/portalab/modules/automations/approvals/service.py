"""Approvals (T016; R7): a destructive step — or a sensitive one without standing approval — waits for an
approver holding ``automation.approve``. Approve (in time, parameters unchanged — hash check) resumes the
execution **once** from that step; reject or expiry leave it ``refused``. Decisions are audited and
emitted as ``automation.approval_decided``; AI never approves anything."""

from typing import Any
from uuid import UUID

from sqlalchemy import select

from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, Forbidden, NotFound
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.automations.definitions.schema import Step
from portalab.modules.automations.models import Approval, Automation, AutomationVersion, Execution
from portalab.modules.automations.observability import metrics
from portalab.modules.automations.runner.runner import Outcome, Runner, params_hash


class ApprovalNotFound(NotFound):
    default_code = "automation.approval_not_found"
    default_title = "Approval not found"


class Approvals:
    def __init__(
        self,
        database: Database,
        runner: Runner,
        audit: AuditSink,
        events: EventPublisher,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.runner = runner
        self.audit = audit
        self.events = events
        self.clock = clock

    async def queue(self, status: str = "pending") -> list[Approval]:
        async with self.database.session() as session:
            rows = await session.execute(
                select(Approval).where(Approval.status == status).order_by(Approval.created_at)
            )
            return list(rows.scalars())

    async def _decide(
        self, actor: Principal, approval_id: UUID, decision: str
    ) -> tuple[Approval, Execution, Automation]:
        if actor.channel != "user":
            raise Forbidden("Only a person can decide an approval.", code="automation.approval_required")
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            approval = await uow.session.get(Approval, approval_id, with_for_update=True)
            if approval is None:
                raise ApprovalNotFound("This approval does not exist.")
            if approval.status != "pending":
                raise Conflict("This approval was already decided.", code="automation.approval_decided")
            execution = await uow.session.get(Execution, approval.execution_id, with_for_update=True)
            automation = await uow.session.get(Automation, execution.automation_id) if execution else None
            assert execution is not None and automation is not None
            expired = approval.expires_at <= now
            if (
                decision == "approved"
                and params_hash(approval.action, approval.params.get("approved_params", {}))
                != approval.params_hash
            ):
                raise Conflict(
                    "The action parameters changed; it cannot be approved.",
                    code="automation.approval_tampered",
                )
            approval.status = "expired" if expired else decision
            approval.decided_by, approval.decided_at = actor.acting_for or actor.user_id, now
            if approval.status != "approved":
                execution.status, execution.error_code, execution.finished_at = (
                    "refused",
                    f"approval_{approval.status}",
                    now,
                )
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action=f"automation.approval_{approval.status}",
                    actor=actor,
                    resource=ResourceRef("automation", str(automation.id)),
                    decision="allow",
                    context={
                        "automation": automation.key,
                        "action": approval.action,
                        "params_hash": approval.params_hash,
                    },
                    sensitive=True,
                ),
            )
            await self.events.publish(
                uow.session,
                "automation.approval_decided",
                {"automation": automation.key, "action": approval.action, "decision": approval.status},
                occurred_at=now,
                actor=actor,
                subject=SubjectRef("automation", str(automation.id)),
                dedup_key=f"automation.approval_decided:{approval.id}",
            )
        metrics.increment(f"automations.approvals.{approval.status}")
        if expired:
            raise Conflict(
                "This approval expired; the action was not executed.", code="automation.approval_expired"
            )
        return approval, execution, automation

    async def approve(self, actor: Principal, approval_id: UUID) -> Outcome:
        approval, execution, automation = await self._decide(actor, approval_id, "approved")
        async with self.database.session() as session:
            version = await session.get(AutomationVersion, (automation.id, execution.version))
        assert version is not None
        pending: list[dict[str, Any]] = approval.params.get("steps", [])
        steps = [
            Step(id=s["id"], action=s["action"], params=s["params"], on_error=s["on_error"]) for s in pending
        ]
        done = [s for s in execution.steps if s.get("status") != "awaiting_approval"]
        return await self.runner.steps(
            execution.id,
            automation,
            version.standing_approvals,
            steps,
            {},
            None,
            execution.depth,
            execution.chain_id,
            path=list(execution.trigger_ref.get("path", [])),
            approved=approval.step_id,
            done=done,
        )

    async def reject(self, actor: Principal, approval_id: UUID) -> None:
        await self._decide(actor, approval_id, "rejected")

    async def expire(self) -> int:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            rows = list(
                (
                    await uow.session.execute(
                        select(Approval)
                        .where(Approval.status == "pending", Approval.expires_at <= now)
                        .with_for_update(skip_locked=True)
                    )
                ).scalars()
            )
            for approval in rows:
                approval.status = "expired"
                execution = await uow.session.get(Execution, approval.execution_id, with_for_update=True)
                if execution is not None and execution.status == "awaiting_approval":
                    execution.status, execution.error_code, execution.finished_at = (
                        "refused",
                        "approval_expired",
                        now,
                    )
        return len(rows)
