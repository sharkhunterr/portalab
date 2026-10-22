"""#98: the maintenance's badge — the maintenance windows under way, for those who manage the services."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select

from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.core.time import utc_now
from portalab.modules.health.models import MaintenanceWindow
from portalab.modules.health.permissions import SERVICES_MANAGE

ENTRY = "health.maintenance"


class MaintenanceAttention:
    def __init__(self, database: Database, authorizer: Authorizer) -> None:
        self.database = database
        self.authorizer = authorizer

    async def counts(self, principal: Principal) -> Mapping[str, int]:
        if not await self.authorizer.is_allowed(principal, SERVICES_MANAGE):
            return {}
        now = utc_now()
        async with self.database.session() as session:
            # under way by the clock too: the job that flips « scheduled » to « active » may lag a little
            active: Any = await session.scalar(
                select(func.count()).where(
                    MaintenanceWindow.status.in_(("scheduled", "active")),
                    MaintenanceWindow.starts_at <= now,
                    MaintenanceWindow.ends_at > now,
                )
            )
        return {ENTRY: int(active or 0)}
