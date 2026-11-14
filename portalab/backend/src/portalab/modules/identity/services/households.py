"""032: what identity asks the household module (``household.profiles``) — which session acts as a live
profile of its master, which accounts are profiles (never dormant, never matched with a service, following
their master's deletion), which ones stay out of the community. Without the module, no account is one."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.household import CAPABILITY as HOUSEHOLD
from portalab.capabilities.household import Household
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.domain.state_machine import AccountState
from portalab.modules.identity.models import User, UserSession


def household(ctx: IdentityContext) -> Household | None:
    providers = ctx.capabilities.system_providers(HOUSEHOLD)
    return providers[0].provider if providers else None


async def acting(ctx: IdentityContext, session: AsyncSession, row: UserSession) -> UUID | None:
    """The live profile a session acts as — ``None`` when it acts as its account, or when that profile is no
    longer usable (gone, or its module switched off)."""
    if row.acting_user_id is None:
        return None
    found = household(ctx)
    if found is None or await found.owner_of(row.acting_user_id) != row.user_id:
        return None
    state = await session.scalar(select(User.state).where(User.id == row.acting_user_id))
    return row.acting_user_id if state == AccountState.ACTIVE.value else None


async def profiles(ctx: IdentityContext) -> frozenset[UUID]:
    found = household(ctx)
    try:
        return await found.profiles() if found is not None else frozenset()
    except Exception:
        return frozenset()


async def profiles_of(ctx: IdentityContext, owner: UUID) -> frozenset[UUID]:
    found = household(ctx)
    try:
        return await found.profiles_of(owner) if found is not None else frozenset()
    except Exception:
        return frozenset()


async def hidden(ctx: IdentityContext) -> frozenset[UUID]:
    found = household(ctx)
    try:
        return await found.hidden() if found is not None else frozenset()
    except Exception:
        return frozenset()
