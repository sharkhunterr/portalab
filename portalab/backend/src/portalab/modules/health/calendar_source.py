"""Calendar source ``maintenance`` (spec 011 T025, owned by 006): maintenance windows overlapping the
requested range, for holders of ``services.read``. Items stay here; the calendar only shows them."""

from datetime import datetime

from sqlalchemy import select

from portalab.capabilities.content import CalendarItem, CalendarSourceResult
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.health.models import MaintenanceWindow


class MaintenanceCalendarSource:
    kind = "maintenance"
    label_key = "calendar:source.maintenance"
    required_permission = "services.read"

    def __init__(self, database: Database, *, clock: Clock | None = None) -> None:
        self.database = database
        self.clock = clock

    @staticmethod
    def _item(row: MaintenanceWindow) -> CalendarItem:
        return CalendarItem(
            source_kind="maintenance",
            source_id=str(row.id),
            type="maintenance",
            title=row.title,
            starts_at=row.starts_at,
            ends_at=row.ends_at,
            reference_tz=row.reference_time_zone,
            status=row.status,
            url_ref=f"/services/{row.service_id}" if row.service_id else "/services",
        )

    async def items(
        self, start: datetime, end: datetime, viewer: Principal, ctx: LocaleContext
    ) -> CalendarSourceResult:
        async with self.database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(MaintenanceWindow).where(
                            MaintenanceWindow.starts_at < end,
                            MaintenanceWindow.ends_at > start,
                            MaintenanceWindow.status != "cancelled",
                        )
                    )
                )
                .scalars()
                .all()
            )
        return CalendarSourceResult(items=[self._item(r) for r in rows], as_of=utc_now(self.clock))

    async def item(self, source_id: str, viewer: Principal) -> CalendarItem | None:
        from uuid import UUID

        try:
            key = UUID(source_id)
        except ValueError:
            return None
        async with self.database.session() as session:
            row = await session.get(MaintenanceWindow, key)
        return self._item(row) if row is not None else None
