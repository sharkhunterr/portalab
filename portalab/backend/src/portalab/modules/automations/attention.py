"""#98: the automations' badge — the approvals an automation waits for, for those who may approve."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select

from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.time import utc_now
from portalab.modules.automations.models import Approval
from portalab.modules.automations.permissions import APPROVE

ENTRY = "automations.approvals"


class ApprovalsAttention:
    def __init__(self, database: Database, authorizer: Authorizer) -> None:
        self.database = database
        self.authorizer = authorizer

    async def counts(self, principal: Principal) -> Mapping[str, int]:
        if not await self.authorizer.is_allowed(principal, APPROVE):
            return {}
        async with self.database.session() as session:
            waiting: Any = await session.scalar(
                select(func.count()).where(Approval.status == "pending", Approval.expires_at > utc_now())
            )
        return {ENTRY: int(waiting or 0)}
