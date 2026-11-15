"""Issue 443: a master switches its household economy — the items' side of it.

To a common pot, each profile's live items are duplicated on the master (activated as its own) and its reserve
items added to the master's reserve. To dispatched profiles, the master gives back what came from them: the
copies (revoked, their effects withdrawn) and the reserve items still there."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select, update

from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.marketplace.activation.service import USABLE, Activation
from portalab.modules.marketplace.models import Ownership, ReserveItem
from portalab.modules.marketplace.observability import log

GONE = ("revoked", "refunded", "expired")


class MarketplacePot:
    def __init__(self, database: Database, activation: Activation, *, clock: Clock | None = None) -> None:
        self.database = database
        self.activation = activation
        self.clock = clock

    async def regroup(self, owner: UUID, profiles: Sequence[UUID], pot: bool) -> None:
        if pot:
            await self._pool(owner, profiles)
        else:
            await self._give_back(owner, profiles)

    async def _pool(self, owner: UUID, profiles: Sequence[UUID]) -> None:
        async with self.database.session() as session:
            items = list(
                (
                    await session.scalars(
                        select(Ownership).where(
                            Ownership.user_id.in_(profiles),
                            Ownership.state.in_(USABLE),
                            ~Ownership.idempotency_key.like("household:%"),
                            ~Ownership.idempotency_key.like("reserve:%"),
                        )
                    )
                ).all()
            )
            kept = list(
                (
                    await session.execute(
                        select(ReserveItem.product_id, ReserveItem.quantity).where(
                            ReserveItem.user_id.in_(profiles), ReserveItem.quantity > 0
                        )
                    )
                )
                .tuples()
                .all()
            )
        for item in items:
            try:
                await self.activation.household_copy(item)
            except Exception:
                log.exception("household item not copied")
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            for product, quantity in kept:
                row = await uow.session.get(ReserveItem, (owner, product), with_for_update=True)
                if row is None:
                    uow.session.add(
                        ReserveItem(
                            user_id=owner,
                            product_id=product,
                            quantity=quantity,
                            household_copies=quantity,
                            updated_at=now,
                            received_at=now,
                        )
                    )
                    await uow.session.flush()
                else:
                    row.quantity += quantity
                    row.household_copies += quantity
                    row.updated_at = now

    async def _give_back(self, owner: UUID, profiles: Sequence[UUID]) -> None:
        now = utc_now(self.clock)
        prefixes = [f"household:{profile}:%" for profile in profiles]
        async with self.database.unit_of_work() as uow:
            session = uow.session
            copies = list(
                (
                    await session.scalars(
                        select(Ownership)
                        .where(
                            Ownership.user_id == owner,
                            Ownership.state.not_in(GONE),
                            or_(*(Ownership.idempotency_key.like(prefix) for prefix in prefixes)),
                        )
                        .with_for_update()
                    )
                ).all()
            )
            for row in copies:
                row.state, row.revoked_at = "revoked", now
                row.revoke_ground, row.revoke_reason = "withdrawn_for_cause", "household dispatched"
            await session.execute(
                update(ReserveItem)
                .where(ReserveItem.user_id == owner, ReserveItem.household_copies > 0)
                .values(
                    quantity=ReserveItem.quantity
                    - func.least(ReserveItem.household_copies, ReserveItem.quantity),
                    household_copies=0,
                    updated_at=now,
                )
            )
        for row in copies:
            await self.activation.deactivate(row)
