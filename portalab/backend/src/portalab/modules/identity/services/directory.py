"""``identity.directory`` capability provider (T015)."""

from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.identity_directory import CAPABILITY, CONTACT, UserSummary
from portalab.capabilities.registry import CapabilityRegistry
from portalab.modules.identity.context import OWNER, IdentityContext
from portalab.modules.identity.domain.state_machine import AccountState, is_active_account
from portalab.modules.identity.models import User


class IdentityDirectoryService:
    def __init__(self, ctx: IdentityContext) -> None:
        self.ctx = ctx

    async def get_user_summary(self, user_id: UUID) -> UserSummary | None:
        async with self.ctx.database.session() as session:
            row = (
                await session.execute(
                    select(User.id, User.display_name, User.state).where(User.id == user_id)
                )
            ).one_or_none()
        if row is None:
            return None
        state = AccountState(row.state)
        deleted = state is AccountState.DELETED
        return UserSummary(
            id=row.id,
            display_name=None if deleted else row.display_name,
            state=state.value,
            is_active=is_active_account(state),
            anonymized=deleted,
        )

    async def is_active_account(self, user_id: UUID) -> bool:
        async with self.ctx.database.session() as session:
            state = (await session.execute(select(User.state).where(User.id == user_id))).scalar_one_or_none()
        return state is not None and is_active_account(AccountState(state))

    async def exists(self, user_id: UUID) -> bool:
        async with self.ctx.database.session() as session:
            found = (await session.execute(select(User.id).where(User.id == user_id))).scalar_one_or_none()
        return found is not None


class IdentityContactService:
    """``identity.contact``: the e-mail address for system delivery only, and the active accounts."""

    def __init__(self, ctx: IdentityContext) -> None:
        self.ctx = ctx

    async def email_of(self, user_id: UUID) -> str | None:
        async with self.ctx.database.session() as session:
            row = (
                await session.execute(select(User.email, User.state).where(User.id == user_id))
            ).one_or_none()
        if row is None or not is_active_account(AccountState(row.state)):
            return None
        return str(row.email) if row.email else None

    async def active_user_ids(self) -> list[UUID]:
        async with self.ctx.database.session() as session:
            rows = await session.execute(select(User.id).where(User.state == AccountState.ACTIVE.value))
            return [row[0] for row in rows]


def register_directory(registry: CapabilityRegistry, ctx: IdentityContext) -> None:
    registry.provide(CAPABILITY, IdentityDirectoryService(ctx), instance_ref="identity", owner=OWNER)
    if not registry.system_providers(CONTACT):
        registry.provide(CONTACT, IdentityContactService(ctx), instance_ref="identity", owner=OWNER)
