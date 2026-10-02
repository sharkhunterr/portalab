"""AccountService — the only writer of ``users.state`` (research R8).

One transaction per transition: state row, append-only history row, ``user.*`` event (dedup key
``user:<id>:<to_state>:<transition_seq>`` so replays never double-apply) and the audit record.
"""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.domain.display_name import (
    clean_display_name,
    display_name_key,
    normalize_login,
)
from portalab.modules.identity.domain.state_machine import AccountState, check_transition, event_for
from portalab.modules.identity.models import AccountStateHistory, Profile, User
from portalab.modules.identity.services.common import (
    Actor,
    DisplayNameTaken,
    UserNotFound,
    audit,
    publish,
    user_ref,
)


class LoginTaken(Exception):
    """Internal signal: callers decide how to answer without enabling enumeration."""


def is_unique_violation(exc: IntegrityError, constraint: str) -> bool:
    return constraint in str(exc.orig)


class AccountService:
    def __init__(self, ctx: IdentityContext) -> None:
        self.ctx = ctx

    async def get_for_update(self, session: AsyncSession, user_id: UUID) -> User:
        user = (
            await session.execute(select(User).where(User.id == user_id).with_for_update())
        ).scalar_one_or_none()
        if user is None:
            raise UserNotFound()
        return user

    async def create_user(
        self,
        session: AsyncSession,
        *,
        login: str,
        display_name: str,
        email: str | None,
        state: AccountState,
        actor: Actor,
        reason: str,
    ) -> User:
        """Insert a user (+ empty profile, first history row) and publish ``user.created``."""
        now = self.ctx.now()
        normalized = normalize_login(login)
        user = User(
            login=normalized,
            login_display=login.strip(),
            display_name=clean_display_name(display_name),
            display_name_key=display_name_key(display_name),
            email=email,
            state=state.value,
            transition_seq=1,
            state_changed_at=now,
            verified_at=now if state is AccountState.ACTIVE else None,
            created_at=now,
            updated_at=now,
        )
        try:
            async with session.begin_nested():
                session.add(user)
                await session.flush()
        except IntegrityError as exc:
            if is_unique_violation(exc, "uq_users_display_name_key"):
                raise DisplayNameTaken() from exc
            if is_unique_violation(exc, "uq_users_login"):
                raise LoginTaken() from exc
            raise
        session.add(Profile(user_id=user.id, updated_at=now))
        session.add(
            AccountStateHistory(
                user_id=user.id,
                transition_seq=1,
                from_state=None,
                to_state=state.value,
                actor_id=actor.user_id,
                actor_kind=actor.kind,
                reason=reason,
                occurred_at=now,
                received_at=now,
            )
        )
        await session.flush()
        await publish(
            self.ctx,
            session,
            "user.created",
            user.id,
            actor=actor.principal,
            occurred_at=now,
            metadata={"state": state.value, "reason": reason},
            dedup_key=f"user:{user.id}:created",
        )
        await audit(
            self.ctx,
            session,
            "user.created",
            actor.principal,
            resource=user_ref(user.id),
            context={"state": state.value, "reason": reason},
            sensitive=actor.kind == "admin",
        )
        return user

    async def transition(
        self,
        session: AsyncSession,
        user: User,
        target: AccountState,
        actor: Actor,
        *,
        reason: str,
        metadata: Mapping[str, Any] | None = None,
        sensitive: bool = False,
    ) -> str:
        """Apply one guarded transition; returns the published event type."""
        current = AccountState(user.state)
        prior = AccountState(user.state_before_deletion) if user.state_before_deletion else None
        check_transition(current, target, actor.kind, prior_state=prior)
        now = self.ctx.now()
        user.transition_seq += 1
        user.state = target.value
        user.state_changed_at = now
        user.updated_at = now
        if target is AccountState.PENDING_DELETION:
            user.state_before_deletion = current.value
        elif current is AccountState.PENDING_DELETION:
            user.state_before_deletion = None
        if target is AccountState.ACTIVE and current is AccountState.PENDING_VERIFICATION:
            user.verified_at = now
        session.add(
            AccountStateHistory(
                user_id=user.id,
                transition_seq=user.transition_seq,
                from_state=current.value,
                to_state=target.value,
                actor_id=actor.user_id,
                actor_kind=actor.kind,
                reason=reason,
                occurred_at=now,
                received_at=now,
            )
        )
        await session.flush()
        event_type = event_for(current, target)
        published = await publish(
            self.ctx,
            session,
            event_type,
            user.id,
            actor=actor.principal,
            occurred_at=now,
            metadata={
                "from_state": current.value,
                "to_state": target.value,
                "reason": reason,
                **(metadata or {}),
            },
            dedup_key=f"user:{user.id}:{target.value}:{user.transition_seq}",
        )
        await audit(
            self.ctx,
            session,
            event_type,
            actor.principal,
            resource=user_ref(user.id),
            context={"from_state": current.value, "to_state": target.value, "reason": reason},
            sensitive=sensitive or actor.kind == "admin",
            event_id=published.event_id,
        )
        return event_type
