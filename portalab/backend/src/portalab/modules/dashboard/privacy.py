"""Privacy participants (T003): the user's dashboard (widget instances: personal data class ``preference``)
is part of the personal-data export and erased with the account (idempotent)."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.core.db import Database
from portalab.modules.dashboard.models import WidgetInstance


class DashboardParticipant:
    def __init__(self, database: Database, erase: object) -> None:
        self.database = database
        self._erase = erase

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(WidgetInstance)
                    .where(WidgetInstance.user_id == user_id)
                    .order_by(WidgetInstance.position)
                )
            ).scalars()
            return [
                ExportRecord(
                    "dashboard.widget",
                    {
                        "widget": r.widget_key,
                        "status": r.status,
                        "position": r.position,
                        "size": [r.w, r.h],
                        "config": r.config,
                    },
                )
                for r in rows
            ]

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        await self._erase(user_id)  # type: ignore[operator]
