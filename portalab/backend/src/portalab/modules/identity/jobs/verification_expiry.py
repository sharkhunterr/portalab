"""Lifecycle job ``verification_expiry`` (T032): Pending Verification accounts whose newest verification
token expired (or that never received one within the TTL) enter the deletion lifecycle (Pending Deletion,
cancellable by the Admin, then final deletion) instead of being silently orphaned (spec 002 edge case)."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select

from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.domain.state_machine import AccountState
from portalab.modules.identity.models import User, VerificationToken
from portalab.modules.identity.services.common import SYSTEM
from portalab.modules.identity.services.deletion import DeletionService

KIND = "identity.verification_expiry"
BATCH = 200


async def expired_pending_users(ctx: IdentityContext) -> list[UUID]:
    now = ctx.now()
    newest = (
        select(VerificationToken.user_id, func.max(VerificationToken.expires_at).label("expires_at"))
        .group_by(VerificationToken.user_id)
        .subquery()
    )
    statement = (
        select(User.id)
        .join(newest, newest.c.user_id == User.id, isouter=True)
        .where(
            User.state == AccountState.PENDING_VERIFICATION.value,
            func.coalesce(
                newest.c.expires_at, User.created_at + timedelta(hours=ctx.config.verification_ttl_hours)
            )
            <= now,
        )
        .order_by(User.id)
        .limit(BATCH)
    )
    async with ctx.database.session() as session:
        return list((await session.execute(statement)).scalars())


async def run(ctx: IdentityContext, deletion: DeletionService) -> int:
    expired = await expired_pending_users(ctx)
    for user_id in expired:
        await deletion.request(SYSTEM, user_id, reason="verification_expired")
    return len(expired)
