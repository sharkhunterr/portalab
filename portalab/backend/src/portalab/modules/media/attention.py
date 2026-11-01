"""#98: the media's badge — the requests waiting for an administrator's approval, for those who manage
the media. #299: « Mon fil »'s — what arrived for a member since they last read it, and what their news
sources published since."""

from collections.abc import Mapping
from contextlib import suppress
from typing import Any

from sqlalchemy import func, select

from portalab.capabilities.content import SOURCE_ITEMS
from portalab.capabilities.registry import CapabilityRegistry
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
    def __init__(self, feed: Feed, capabilities: CapabilityRegistry) -> None:
        self.feed = feed
        self.capabilities = capabilities

    async def counts(self, principal: Principal) -> Mapping[str, int]:
        user = principal.acting_for or principal.user_id
        if user is None:
            return {}
        unread = await self.feed.unread(user)
        seen = await self.feed.seen_at(user)  # never opened: the news are not new yet, as the feed shows them
        providers = self.capabilities.system_providers(SOURCE_ITEMS)
        if seen is not None and providers:
            with suppress(Exception):  # the news count nothing while their module fails
                unread += await providers[0].provider.published_since(user, seen)
        return {FEED: unread}
