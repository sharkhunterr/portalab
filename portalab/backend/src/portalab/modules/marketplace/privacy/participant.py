"""Privacy participant (T003; R6, decided 2026-10-01, strict CD-005): at final deletion every funding of
the user still holding reserved Coins is marked ``destroyed_on_deletion`` whatever the project state — the
013 participant releases and then destroys the reservations with the account's remaining Coins (never a
transfer to the project, never a refund); project totals drop accordingly (they are computed live). The
rows stay bound to the tombstoned user id with amounts only. Export lists the user's own fundings, and
(#81) the boosters they opened and their reserve — both erased with the account."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select

from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.marketplace.models import BoosterOpening, Equipped, ProjectFunding, ReserveItem


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
            openings = list(
                (
                    await session.execute(select(BoosterOpening).where(BoosterOpening.user_id == user_id))
                ).scalars()
            )
            reserve = list(
                (await session.execute(select(ReserveItem).where(ReserveItem.user_id == user_id))).scalars()
            )
        # #81: the boosters opened and what came out of them, the items kept in the reserve
        extra = [
            ExportRecord(
                "marketplace.booster_opening",
                {
                    "booster": o.booster_key,
                    "price": o.price,
                    "refund": o.refund,
                    "cards": o.drawn,
                    "opened_at": o.opened_at.isoformat(),
                },
            )
            for o in openings
        ] + [
            ExportRecord("marketplace.reserve", {"product": str(r.product_id), "quantity": r.quantity})
            for r in reserve
        ]
        return extra + [
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
            # 027: what the member wore on their profile goes with the account
            await uow.session.execute(delete(Equipped).where(Equipped.user_id == user_id))
            # #81: the boosters opened and the reserve go with it too (amounts stay in the ledger)
            await uow.session.execute(delete(BoosterOpening).where(BoosterOpening.user_id == user_id))
            await uow.session.execute(delete(ReserveItem).where(ReserveItem.user_id == user_id))
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
