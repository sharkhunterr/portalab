"""027: « came today » — ``user.visited`` once a day per member, at the sign-in and at the first request of a
new day of a session kept open (a member who stays signed in for weeks still visits each day). The day is
the economy's (``economy.timezone``), the one daily quests count in; one event per day (dedup)."""

import time
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.config import CAPABILITY as CONFIG
from portalab.core.authz_port import Principal
from portalab.modules.identity.context import IdentityContext
from portalab.modules.identity.services.common import publish

_zone: tuple[float, ZoneInfo] | None = None


async def _timezone(ctx: IdentityContext) -> ZoneInfo:
    global _zone
    if _zone is not None and time.monotonic() - _zone[0] < 300:
        return _zone[1]
    zone = ZoneInfo("UTC")
    try:
        providers = ctx.capabilities.system_providers(CONFIG)
        if providers:
            zone = ZoneInfo(str((await providers[0].provider.get("economy.timezone")).value or "UTC"))
    except Exception:  # noqa: S110 — the day falls back to UTC's
        pass
    _zone = (time.monotonic(), zone)
    return zone


async def day_of(ctx: IdentityContext, at: datetime) -> str:
    return at.astimezone(await _timezone(ctx)).date().isoformat()


async def record_visit(
    ctx: IdentityContext,
    session: AsyncSession,
    user_id: UUID,
    now: datetime,
    *,
    since: datetime | None = None,
) -> None:
    """Publishes today's visit unless ``since`` (the session's previous activity) was already today."""
    day = await day_of(ctx, now)
    if since is not None and await day_of(ctx, since) == day:
        return
    await publish(
        ctx,
        session,
        "user.visited",
        user_id,
        actor=Principal(user_id=user_id),
        occurred_at=now,
        metadata={"day": day},
        dedup_key=f"user.visited:{user_id}:{day}",
    )
