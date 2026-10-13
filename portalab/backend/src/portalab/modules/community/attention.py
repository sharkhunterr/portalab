"""#98: the community's badge — the proposals waiting for a moderator, for those who may moderate."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select

from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.modules.community.models import Proposal
from portalab.modules.community.permissions import MODERATE

ENTRY = "community.moderation"


class ModerationAttention:
    def __init__(self, database: Database, authorizer: Authorizer) -> None:
        self.database = database
        self.authorizer = authorizer

    async def counts(self, principal: Principal) -> Mapping[str, int]:
        if not await self.authorizer.is_allowed(principal, MODERATE):
            return {}
        async with self.database.session() as session:
            waiting: Any = await session.scalar(
                select(func.count()).select_from(Proposal).where(Proposal.status == "pending_moderation")
            )
        return {ENTRY: int(waiting or 0)}
