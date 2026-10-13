"""#98: the shop's badge — the purchases waiting for an administrator's decision (a film in 4K with the
member's wishes, a service's access…), for those who may decide them."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select

from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.modules.marketplace.models import MarketRequest
from portalab.modules.marketplace.permissions import MANAGE

ENTRY = "marketplace.admin_requests"


class ShopAttention:
    def __init__(self, database: Database, authorizer: Authorizer) -> None:
        self.database = database
        self.authorizer = authorizer

    async def counts(self, principal: Principal) -> Mapping[str, int]:
        if not await self.authorizer.is_allowed(principal, MANAGE):
            return {}
        async with self.database.session() as session:
            waiting: Any = await session.scalar(
                select(func.count()).select_from(MarketRequest).where(MarketRequest.state == "pending")
            )
        return {ENTRY: int(waiting or 0)}
