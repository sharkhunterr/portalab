"""Job ``prune_sessions``: deletes session rows expired or revoked for more than 30 days (retention of the
technical ``sessions`` data, plan §1)."""

from datetime import timedelta

from sqlalchemy import delete, or_

from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.models import UserSession

KIND = "identity.prune_sessions"
RETENTION = timedelta(days=30)


async def run(ctx: IdentityContext) -> int:
    cutoff = ctx.now() - RETENTION
    async with ctx.database.unit_of_work() as uow:
        result = await uow.session.execute(
            delete(UserSession).where(or_(UserSession.expires_at < cutoff, UserSession.revoked_at < cutoff))
        )
    return int(getattr(result, "rowcount", 0) or 0)
