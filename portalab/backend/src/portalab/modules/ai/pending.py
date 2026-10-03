"""Pending sensitive actions (T017; FR-020): a ``sensitive`` tool call never executes inline.

The action is stored with the exact parameters, a hash binding them and a **tool-generated** summary;
only its owner, from their own session (``channel=user`` — never the AI), may confirm or decline before
it expires. Confirmation goes through the authorization ``ConfirmationService`` (token bound to the
permission and the parameters hash), then the tool runs **once** as the AI principal acting for the user
(idempotent: a second confirm returns the stored outcome). Audit entries carry ids and hashes, never the
conversation text."""

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select, update

from portalab.capabilities.ai import AITool, ToolResult
from portalab.capabilities.confirmations import CAPABILITY as CONFIRMATIONS
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Forbidden, Unavailable
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.ai.errors import ActionExpired, ActionNotFound
from portalab.modules.ai.models import PendingAction
from portalab.modules.ai.observability import metrics
from portalab.modules.ai.principal import ai_principal, subject_of
from portalab.modules.ai.redaction import redact


def params_hash(tool: str, params: Mapping[str, Any]) -> str:
    material = json.dumps({"tool": tool, "params": params}, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class PendingView:
    id: UUID
    tool: str
    summary: str
    status: str
    expires_at: datetime
    created_at: datetime
    conversation_id: UUID | None = None
    result: Mapping[str, Any] | None = None


def view(row: PendingAction) -> PendingView:
    return PendingView(
        row.id,
        row.tool,
        row.summary,
        row.status,
        row.expires_at,
        row.created_at,
        row.conversation_id,
        row.result,
    )


class Runner(Protocol):
    async def run(self, tool: AITool, acting: Principal, params: Mapping[str, Any]) -> ToolResult: ...


class PendingActions:
    def __init__(
        self,
        database: Database,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        ttl_minutes: Callable[[], int],
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.events = events
        self.audit = audit
        self.capabilities = capabilities
        self.ttl_minutes = ttl_minutes
        self.clock = clock
        self.resolve_tool: Callable[[str], AITool | None] = lambda name: None
        self.runner: Runner | None = None

    async def create(
        self, principal: Principal, tool: AITool, params: dict[str, Any], *, conversation_id: UUID | None
    ) -> PendingView:
        now = utc_now(self.clock)
        try:
            summary = str(tool.summarize(params))[:400]
        except Exception:
            summary = tool.name
        row = PendingAction(
            user_id=subject_of(principal),
            conversation_id=conversation_id,
            tool=tool.name,
            params=params,
            params_hash=params_hash(tool.name, params),
            summary=summary or tool.name,
            status="pending",
            created_at=now,
            expires_at=now + timedelta(minutes=max(1, self.ttl_minutes())),
        )
        async with self.database.unit_of_work() as uow:
            uow.session.add(row)
            await uow.session.flush()
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action="ai.action_proposed",
                    actor=ai_principal(principal),
                    resource=ResourceRef("ai_action", str(row.id)),
                    result="success",
                    context={
                        "tool": tool.name,
                        "params_hash": row.params_hash,
                        "conversation": str(conversation_id),
                    },
                    sensitive=True,
                ),
            )
            return view(row)

    async def get(self, principal: Principal, action_id: UUID) -> PendingView:
        async with self.database.session() as session:
            row = await session.get(PendingAction, action_id)
        if row is None or principal.channel != "user" or row.user_id != principal.user_id:
            raise ActionNotFound("This action does not exist.")
        return view(self._expired_view(row))

    def _expired_view(self, row: PendingAction) -> PendingAction:
        if row.status == "pending" and row.expires_at <= utc_now(self.clock):
            row.status = "expired"
        return row

    def _owner_only(self, principal: Principal) -> None:
        if principal.channel != "user" or principal.user_id is None:
            raise Forbidden(
                "Only the user can confirm an action, from their own session.",
                code="ai.confirmation_forbidden",
            )

    async def _event(self, session: Any, name: str, row: PendingAction, actor: Principal | None) -> None:
        await self.events.publish(
            session,
            name,
            {"tool": row.tool, "action": str(row.id)},
            occurred_at=utc_now(self.clock),
            actor=actor,
            subject=SubjectRef("ai_action", str(row.id)),
            dedup_key=f"{name}:{row.id}",
        )

    async def decline(self, principal: Principal, action_id: UUID) -> PendingView:
        self._owner_only(principal)
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(PendingAction, action_id, with_for_update=True)
            if row is None or row.user_id != principal.user_id:
                raise ActionNotFound("This action does not exist.")
            if row.status in ("declined", "expired"):
                return view(row)
            if row.status != "pending":
                raise ActionExpired("This action was already confirmed.")
            row.status = "declined"
            await self._event(uow.session, "ai.action_declined", row, principal)
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action="ai.action_declined",
                    actor=principal,
                    resource=ResourceRef("ai_action", str(row.id)),
                    context={"tool": row.tool, "params_hash": row.params_hash},
                    sensitive=True,
                ),
            )
        metrics.increment("ai.pending.declined")
        return view(row)

    async def confirm(self, principal: Principal, action_id: UUID) -> PendingView:
        self._owner_only(principal)
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            row = await uow.session.get(PendingAction, action_id, with_for_update=True)
            if row is None or row.user_id != principal.user_id:
                raise ActionNotFound("This action does not exist.")
            if row.status in ("executed", "failed", "confirmed"):
                return view(row)  # idempotent: the action ran (or is running) once
            if row.status != "pending" or row.expires_at <= now:
                raise ActionExpired("This action expired or was declined; ask the assistant again.")
            tool = self.resolve_tool(row.tool)
            if tool is None:
                raise ActionExpired("This action is no longer available.")
            if params_hash(row.tool, row.params) != row.params_hash:
                raise ActionExpired("This action was altered and cannot be confirmed.")
            row.status, row.confirmed_at = "confirmed", now
            params, digest = dict(row.params), row.params_hash
        acting = ai_principal(principal)
        await self._bind_confirmation(acting, tool, action_id, digest)
        assert self.runner is not None
        result = await self.runner.run(tool, acting, params)
        status = "executed" if result.state in ("ok", "partial", "stale") else "failed"
        outcome = {"state": result.state, "detail": result.detail, "data": redact(result.data)}
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                update(PendingAction)
                .where(PendingAction.id == action_id)
                .values(status=status, result=outcome)
            )
            row = await uow.session.get(PendingAction, action_id)
            assert row is not None
            await self._event(uow.session, "ai.action_confirmed", row, principal)
            await self.audit.record(
                uow.session,
                AuditRecord(
                    action="ai.action_confirmed",
                    actor=acting,
                    resource=ResourceRef("ai_action", str(action_id)),
                    decision="allow",
                    result="success" if status == "executed" else "failure",
                    context={
                        "tool": row.tool,
                        "params_hash": digest,
                        "conversation": str(row.conversation_id),
                    },
                    sensitive=True,
                ),
            )
        metrics.increment(f"ai.pending.{status}")
        return view(row)

    async def _bind_confirmation(self, acting: Principal, tool: AITool, action_id: UUID, digest: str) -> None:
        providers = self.capabilities.system_providers(CONFIRMATIONS)
        if not providers:
            raise Unavailable("Confirmations are unavailable.", code="ai.unavailable")
        confirmations = providers[0].provider
        resource = ResourceRef("ai_action", str(action_id))
        token = await confirmations.issue(acting, tool.required_permission, resource, digest)
        if not await confirmations.consume(token, acting, tool.required_permission, resource, digest):
            raise ActionExpired("The confirmation could not be verified.")

    async def expire(self) -> int:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            rows = (
                (
                    await uow.session.execute(
                        select(PendingAction)
                        .where(PendingAction.status == "pending", PendingAction.expires_at <= now)
                        .with_for_update(skip_locked=True)
                        .limit(500)
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                row.status = "expired"
                await self._event(uow.session, "ai.action_expired", row, None)
        if rows:
            metrics.increment("ai.pending.expired", len(rows))
        return len(rows)
