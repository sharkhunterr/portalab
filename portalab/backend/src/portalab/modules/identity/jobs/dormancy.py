"""Lifecycle job ``mark_inactive`` (T035): Active accounts without sign-in for ``identity.dormancyDays``
become Inactive (data preserved, excluded from "active account" eligibility); signing in again returns
them to Active."""

from datetime import timedelta

from sqlalchemy import func, select

from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.domain.state_machine import AccountState
from portalab.modules.identity.models import User
from portalab.modules.identity.services.account_service import AccountService
from portalab.modules.identity.services.common import SYSTEM

KIND = "identity.mark_inactive"
BATCH = 200


async def run(ctx: IdentityContext, accounts: AccountService) -> int:
    threshold = ctx.now() - timedelta(days=ctx.config.dormancy_days)
    last_activity = func.coalesce(User.last_sign_in_at, User.verified_at, User.created_at)
    async with ctx.database.session() as session:
        candidates = list(
            (
                await session.execute(
                    select(User.id)
                    .where(User.state == AccountState.ACTIVE.value, last_activity <= threshold)
                    .order_by(User.id)
                    .limit(BATCH)
                )
            ).scalars()
        )
    changed = 0
    for user_id in candidates:
        async with ctx.database.unit_of_work() as uow:
            user = await accounts.get_for_update(uow.session, user_id)
            activity = user.last_sign_in_at or user.verified_at or user.created_at
            if user.state != AccountState.ACTIVE.value or activity > threshold:
                continue  # signed in meanwhile
            await accounts.transition(uow.session, user, AccountState.INACTIVE, SYSTEM, reason="dormancy")
            changed += 1
    return changed
