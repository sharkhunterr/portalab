"""#98: the announcements' badge — the banners showing to the members right now, for those who broadcast
(one left showing by mistake is seen at a glance)."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select

from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.time import utc_now
from portalab.modules.notifications.models import Announcement
from portalab.modules.notifications.permissions import NOTIFICATIONS_BROADCAST

ENTRY = "notifications.announcements"


class AnnouncementsAttention:
    def __init__(self, database: Database, authorizer: Authorizer) -> None:
        self.database = database
        self.authorizer = authorizer

    async def counts(self, principal: Principal) -> Mapping[str, int]:
        if not await self.authorizer.is_allowed(principal, NOTIFICATIONS_BROADCAST):
            return {}
        now = utc_now()
        async with self.database.session() as session:
            showing: Any = await session.scalar(
                select(func.count()).where(
                    Announcement.banner.is_(True),
                    Announcement.ended_at.is_(None),
                    Announcement.banner_until.is_(None) | (Announcement.banner_until > now),
                )
            )
        return {ENTRY: int(showing or 0)}
