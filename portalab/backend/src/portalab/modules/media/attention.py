"""#98: the media's badge — the requests waiting for an administrator's approval, for those who manage
the media. #299: « Mon fil »'s — what arrived for a member since they last read it."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select

from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.modules.media.feed import Feed
from portalab.modules.media.models import MediaRequest
from portalab.modules.media.permissions import MEDIA_MANAGE

ENTRY = "media.requests_admin"


class RequestsAttention:
    def __init__(self, database: Database, authorizer: Authorizer) -> None:
        self.database = database
        self.authorizer = authorizer

    async def counts(self, principal: Principal) -> Mapping[str, int]:
        if not await self.authorizer.is_allowed(principal, MEDIA_MANAGE):
            return {}
        async with self.database.session() as session:
            waiting: Any = await session.scalar(
                select(func.count()).select_from(MediaRequest).where(MediaRequest.state == "pending")
            )
        return {ENTRY: int(waiting or 0)}


FEED = "media.feed"


class FeedAttention:
    def __init__(self, feed: Feed) -> None:
        self.feed = feed

    async def counts(self, principal: Principal) -> Mapping[str, int]:
        user = principal.acting_for or principal.user_id
        if user is None:
            return {}
        return {FEED: await self.feed.unread(user)}
