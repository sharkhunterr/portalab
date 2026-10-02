"""Administrative account operations (T034, T047): suspend / reactivate, user listing, Admin transfer.

Routes require ``users.manage`` / ``users.admin.transfer``; the services additionally protect the sole Admin
(never suspended, deleted or demoted except through a transfer) and revoke sessions immediately on
suspension (OQ-10 default).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.admin_authority import AdminAuthorityError
from portalab.core.authz_port import Principal
from portalab.core.errors import BadRequest, Conflict
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.domain.state_machine import AccountState
from portalab.modules.identity.models import User
from portalab.modules.identity.observability import metrics
from portalab.modules.identity.services.account_service import AccountService
from portalab.modules.identity.services.common import (
    SoleAdminProtected,
    admin_actor,
    audit,
    publish,
    user_ref,
)
from portalab.modules.identity.services.sessions import SessionService

MAX_PAGE = 100


@dataclass(frozen=True, slots=True)
class UserRow:
    id: UUID
    login: str | None
    display_name: str | None
    state: str
    created_at: datetime
    last_sign_in_at: datetime | None


@dataclass(frozen=True, slots=True)
class UserPage:
    items: list[UserRow]
    next_cursor: str | None


class AdminOperations:
    def __init__(self, ctx: IdentityContext, accounts: AccountService, sessions: SessionService) -> None:
        self.ctx = ctx
        self.accounts = accounts
        self.sessions = sessions

    async def suspend(self, principal: Principal, user_id: UUID, reason: str) -> None:
        authority = self.ctx.admin_authority()
        async with self.ctx.database.unit_of_work() as uow:
            if await authority.is_admin(uow.session, user_id):
                raise SoleAdminProtected("The Admin account cannot be suspended.")
            user = await self.accounts.get_for_update(uow.session, user_id)
            await self.accounts.transition(
                uow.session, user, AccountState.SUSPENDED, admin_actor(principal), reason=reason
            )
            revoked = await self.sessions.revoke_all(uow.session, user_id, self.ctx.now(), "suspended")
        metrics.increment("identity.sessions.revoked", revoked)

    async def reactivate(self, principal: Principal, user_id: UUID, reason: str) -> None:
        async with self.ctx.database.unit_of_work() as uow:
            user = await self.accounts.get_for_update(uow.session, user_id)
            await self.accounts.transition(
                uow.session, user, AccountState.ACTIVE, admin_actor(principal), reason=reason
            )

    async def list_users(self, *, limit: int, cursor: str | None, state: str | None) -> UserPage:
        limit = max(1, min(limit, MAX_PAGE))
        statement = select(User).order_by(User.id).limit(limit + 1)
        if cursor:
            try:
                statement = statement.where(User.id > UUID(cursor))
            except ValueError as exc:
                raise BadRequest("Invalid cursor.", code="pagination.invalid_cursor") from exc
        if state:
            statement = statement.where(User.state == state)
        async with self.ctx.database.session() as session:
            users = list((await session.execute(statement)).scalars())
        page = users[:limit]
        items = [
            UserRow(u.id, u.login_display, u.display_name, u.state, u.created_at, u.last_sign_in_at)
            for u in page
        ]
        return UserPage(items, str(page[-1].id) if len(users) > limit else None)

    async def transfer_admin(self, principal: Principal, target_id: UUID) -> None:
        """Atomic hand-over through ``authz.admin_authority``: exactly one Admin before and after."""
        if principal.user_id is None:
            raise SoleAdminProtected()
        if target_id == principal.user_id:
            raise Conflict("You already hold the Admin role.", code="admin.transfer_to_self")
        authority = self.ctx.admin_authority()
        now = self.ctx.now()
        async with self.ctx.database.unit_of_work() as uow:
            target = await self.accounts.get_for_update(uow.session, target_id)
            if target.state != AccountState.ACTIVE.value:
                raise Conflict(
                    "The Admin role can only go to an active account.", code="admin.transfer_target_inactive"
                )
            try:
                await authority.transfer_admin(uow.session, principal.user_id, target_id, principal)
            except AdminAuthorityError as exc:
                raise SoleAdminProtected("The transfer would not leave exactly one Admin.") from exc
            await publish(
                self.ctx,
                uow.session,
                "user.admin_transferred",
                target_id,
                actor=principal,
                occurred_at=now,
                metadata={"from_user": str(principal.user_id), "to_user": str(target_id)},
            )
            await audit(
                self.ctx,
                uow.session,
                "user.admin_transferred",
                principal,
                resource=user_ref(target_id),
                decision="allow",
                context={"from_user": str(principal.user_id), "to_user": str(target_id)},
                sensitive=True,
            )
            # privilege change: the former Admin's other sessions are ended (research R1 rotation rule)
            await self.sessions.revoke_all(
                uow.session, principal.user_id, now, "admin", except_id=principal.session_id
            )
