"""``identity.directory`` capability provider (T015) and ``identity.members`` (Community 012)."""

import unicodedata
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.identity_directory import (
    CAPABILITY,
    CONTACT,
    MEMBERS,
    MemberEntry,
    MemberPage,
    UserSummary,
)
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


class IdentityMembersService:
    """``identity.members``: active accounts with a display name, matched on the normalized name only."""

    def __init__(self, ctx: IdentityContext) -> None:
        self.ctx = ctx

    async def active_members(
        self, *, query: str | None = None, offset: int = 0, limit: int = 30, newest: bool = False
    ) -> MemberPage:
        limit = max(1, min(limit, 100))
        statement = select(User.id, User.display_name, User.created_at).where(
            User.state == AccountState.ACTIVE.value, User.display_name.is_not(None)
        )
        if query and query.strip():
            needle = unicodedata.normalize("NFKC", query.strip().casefold())[:64]
            statement = statement.where(User.display_name_key.contains(needle, autoescape=True))
        order = (User.created_at.desc(), User.id) if newest else (User.display_name_key, User.id)
        async with self.ctx.database.session() as session:
            rows = (
                await session.execute(statement.order_by(*order).offset(max(0, offset)).limit(limit + 1))
            ).all()
        items = tuple(MemberEntry(r.id, r.display_name, r.created_at) for r in rows[:limit])
        return MemberPage(items, offset + limit if len(rows) > limit else None)


def register_directory(registry: CapabilityRegistry, ctx: IdentityContext) -> None:
    registry.provide(CAPABILITY, IdentityDirectoryService(ctx), instance_ref="identity", owner=OWNER)
    if not registry.system_providers(MEMBERS):
        registry.provide(MEMBERS, IdentityMembersService(ctx), instance_ref="identity", owner=OWNER)
    if not registry.system_providers(CONTACT):
        registry.provide(CONTACT, IdentityContactService(ctx), instance_ref="identity", owner=OWNER)
