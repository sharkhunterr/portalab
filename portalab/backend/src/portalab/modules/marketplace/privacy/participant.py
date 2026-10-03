"""Privacy participant (T003; R6, decided 2026-10-01, strict CD-005): at final deletion every funding of
the user still holding reserved Coins is marked ``destroyed_on_deletion`` whatever the project state — the
013 participant releases and then destroys the reservations with the account's remaining Coins (never a
transfer to the project, never a refund); project totals drop accordingly (they are computed live). The
rows stay bound to the tombstoned user id with amounts only. Export lists the user's own fundings."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.marketplace.models import ProjectFunding


class MarketplaceParticipant:
    def __init__(self, database: Database, *, clock: Clock | None = None) -> None:
        self.database = database
        self.clock = clock

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        async with self.database.session() as session:
            rows = list(
                (
                    await session.execute(select(ProjectFunding).where(ProjectFunding.user_id == user_id))
                ).scalars()
            )
        return [
            ExportRecord(
                "marketplace.funding",
                {
                    "project": str(r.project_id),
                    "amount": r.amount,
                    "status": r.status,
                    "created_at": r.created_at.isoformat(),
                },
            )
            for r in rows
        ]

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            rows = (
                await uow.session.execute(
                    select(ProjectFunding)
                    .where(
                        ProjectFunding.user_id == user_id,
                        ProjectFunding.status.in_(("reserved", "partially_consumed")),
                    )
                    .with_for_update()
                )
            ).scalars()
            for funding in rows:
                funding.tranches = [
                    {**t, "status": "destroyed"} if t["status"] == "reserved" else dict(t)
                    for t in funding.tranches
                ]
                funding.status, funding.resolved_at = "destroyed_on_deletion", now
