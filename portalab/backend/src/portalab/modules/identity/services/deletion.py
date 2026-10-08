"""Deletion saga (T043): request → Pending Deletion (grace, cancellable) → final deletion (tombstone).

* request: guarded transition, open ``deletion_requests`` row, every session revoked, ``finalize_deletion``
  job scheduled at ``due_at``; the sole Admin is refused (FR-030);
* cancel: only before ``due_at`` and before finalization (FR-025), restores the prior state;
* finalize: runs every registered ``privacy.erasure_participant`` (idempotent, per-participant status kept in
  ``saga_state``; a failing participant is retried by the job and blocks finalization until it succeeds),
  then tombstones the account: classified personal columns nulled, ``id`` kept so ledgers and history stay
  consistent but reference an anonymized subject; the display name is released (OQ-8 default).
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.privacy_participants import ERASURE_CAPABILITY
from portalab.core.authz_port import Principal
from portalab.core.errors import Conflict, NotFound
from portalab.core.jobs.queue import enqueue
from portalab.core.tombstone import scrub
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.domain.state_machine import AccountState
from portalab.modules.identity.models import DeletionRequest, ExternalIdentity, User
from portalab.modules.identity.observability import log_event, metrics
from portalab.modules.identity.services.account_service import AccountService
from portalab.modules.identity.services.common import (
    SYSTEM,
    Actor,
    SoleAdminProtected,
    publish,
)
from portalab.modules.identity.services.sessions import SessionService

FINALIZE_JOB = "identity.finalize_deletion"


class DeletionNotCancellable(Conflict):
    default_code = "user.deletion_not_cancellable"
    default_title = "The deletion can no longer be cancelled"


class SagaIncomplete(RuntimeError):
    """At least one erasure participant failed; the job retries the saga later."""


class DeletionService:
    def __init__(self, ctx: IdentityContext, accounts: AccountService, sessions: SessionService) -> None:
        self.ctx = ctx
        self.accounts = accounts
        self.sessions = sessions

    async def _open_request(self, session: AsyncSession, user_id: UUID) -> DeletionRequest | None:
        return (
            await session.execute(
                select(DeletionRequest)
                .where(
                    DeletionRequest.user_id == user_id,
                    DeletionRequest.cancelled_at.is_(None),
                    DeletionRequest.finalized_at.is_(None),
                )
                .with_for_update()
            )
        ).scalar_one_or_none()

    async def request(self, actor: Actor, user_id: UUID, *, reason: str) -> DeletionRequest:
        authority = self.ctx.admin_authority()
        now = self.ctx.now()
        due_at = now + timedelta(days=self.ctx.config.deletion_grace_days)
        async with self.ctx.database.unit_of_work() as uow:
            if await authority.is_admin(uow.session, user_id):
                raise SoleAdminProtected(
                    "The Admin account cannot be deleted; transfer the Admin role first."
                )
            user = await self.accounts.get_for_update(uow.session, user_id)
            prior = user.state
            await self.accounts.transition(
                uow.session,
                user,
                AccountState.PENDING_DELETION,
                actor,
                reason=reason,
                metadata={"due_at": due_at.isoformat()},
                sensitive=True,
            )
            user.deletion_requested_at = now
            user.deletion_due_at = due_at
            request = DeletionRequest(
                user_id=user_id,
                requested_by=actor.user_id,
                requested_at=now,
                due_at=due_at,
                prior_state=prior,
                saga_state={},
            )
            uow.session.add(request)
            await uow.session.flush()
            await self.sessions.revoke_all(uow.session, user_id, now, "deleted")
            await enqueue(
                uow.session,
                kind=FINALIZE_JOB,
                payload={"request_id": str(request.id)},
                dedup_key=f"{FINALIZE_JOB}:{request.id}",
                run_at=due_at,
                max_attempts=20,
                clock=self.ctx.clock,
            )
        return request

    async def cancel(self, actor: Actor, user_id: UUID) -> None:
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            user = await self.accounts.get_for_update(uow.session, user_id)
            request = await self._open_request(uow.session, user_id)
            if user.state != AccountState.PENDING_DELETION.value or request is None:
                raise DeletionNotCancellable("There is no pending deletion for this account.")
            if now >= request.due_at:
                raise DeletionNotCancellable(
                    "The grace period is over; the deletion can no longer be cancelled."
                )
            await self.accounts.transition(
                uow.session,
                user,
                AccountState(request.prior_state),
                actor,
                reason="deletion_cancelled",
                sensitive=True,
            )
            user.deletion_requested_at = None
            user.deletion_due_at = None
            request.cancelled_at = now
            request.cancelled_by = actor.user_id

    async def pending_for(self, user_id: UUID) -> DeletionRequest | None:
        async with self.ctx.database.session() as session:
            return (
                await session.execute(
                    select(DeletionRequest).where(
                        DeletionRequest.user_id == user_id,
                        DeletionRequest.cancelled_at.is_(None),
                        DeletionRequest.finalized_at.is_(None),
                    )
                )
            ).scalar_one_or_none()

    async def finalize(self, request_id: UUID) -> bool:
        """Run the saga; True when the account is (already) deleted or the request was cancelled."""
        now = self.ctx.now()
        async with self.ctx.database.session() as session:
            request = await session.get(DeletionRequest, request_id)
        if request is None:
            raise NotFound()
        if request.cancelled_at is not None or request.finalized_at is not None:
            return True
        if now < request.due_at:
            return False
        authority = self.ctx.admin_authority()
        async with self.ctx.database.session() as session:
            if await authority.is_admin(session, request.user_id):
                raise SoleAdminProtected()
        await self._run_participants(request)
        async with self.ctx.database.unit_of_work() as uow:
            current = await uow.session.get(DeletionRequest, request_id, with_for_update=True)
            if current is None or current.cancelled_at is not None or current.finalized_at is not None:
                return True
            user = await self.accounts.get_for_update(uow.session, current.user_id)
            await self._tombstone(uow.session, user, now)
            current.finalized_at = now
        log_event("identity.deletion_finalized", request_id=str(request_id))
        return True

    async def _run_participants(self, request: DeletionRequest) -> None:
        state: dict[str, Any] = dict(request.saga_state or {})
        failed: list[str] = []
        for registration in self.ctx.capabilities.system_providers(ERASURE_CAPABILITY):
            ref = registration.instance_ref
            entry = dict(state.get(ref) or {})
            if entry.get("status") == "done":
                continue
            try:
                await registration.provider.erase(request.user_id, "final")
            except Exception as exc:
                entry = {
                    "status": "failed",
                    "attempts": int(entry.get("attempts", 0)) + 1,
                    "error": type(exc).__name__,
                }
                failed.append(ref)
                metrics.increment("identity.deletion.participant_failed")
                log_event("identity.deletion_participant_failed", participant=ref, error=type(exc).__name__)
            else:
                entry = {"status": "done", "attempts": int(entry.get("attempts", 0)) + 1}
            state[ref] = entry
            await self._save_state(request.id, ref, entry)
        if failed:
            raise SagaIncomplete(f"erasure participants failed: {', '.join(sorted(failed))}")

    async def _save_state(self, request_id: UUID, ref: str, entry: dict[str, Any]) -> None:
        async with self.ctx.database.unit_of_work() as uow:
            row = await uow.session.get(DeletionRequest, request_id, with_for_update=True)
            if row is not None:
                row.saga_state = {**(row.saga_state or {}), ref: entry}

    async def _tombstone(self, session: AsyncSession, user: User, now: datetime) -> None:
        await publish(
            self.ctx,
            session,
            "user.anonymized",
            user.id,
            actor=SYSTEM.principal,
            occurred_at=now,
            dedup_key=f"user:{user.id}:anonymized",
        )
        await self.accounts.transition(
            session, user, AccountState.DELETED, SYSTEM, reason="final_deletion", sensitive=True
        )
        user.deleted_at = now
        user.deletion_due_at = None
        await session.flush()
        await scrub(session, User.__table__, where=User.__table__.c.id == user.id)  # type: ignore[arg-type]
        # 027: the single sign-on accounts linked to the member go with the account
        await session.execute(delete(ExternalIdentity).where(ExternalIdentity.user_id == user.id))


def requester(principal: Principal, *, as_admin: bool) -> Actor:
    return Actor("admin" if as_admin else "self", principal)
