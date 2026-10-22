"""Privacy participant (issue 229): the cards are not personal; the copies a member owns and the packs they
were given are exported with their data and erased with them."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select

from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.core.db import Database
from portalab.modules.cards.models import Card, CardSet, Copy, Pack


class CardsParticipant:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        async with self.database.session() as session:
            rows = await session.execute(
                select(CardSet.name, Card.number, Card.name, Copy.variant, Copy.acquired_at)
                .join(Card, Card.id == Copy.card_id)
                .join(CardSet, CardSet.key == Card.set_key)
                .where(Copy.user_id == user_id)
            )
            return [
                ExportRecord(
                    "cards.copy",
                    {"set": s, "number": n, "card": c, "variant": v, "acquired_at": at.isoformat()},
                )
                for s, n, c, v, at in rows
            ]

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(delete(Copy).where(Copy.user_id == user_id))
            await uow.session.execute(delete(Pack).where(Pack.user_id == user_id))
