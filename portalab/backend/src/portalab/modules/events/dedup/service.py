"""``events.dedup_keys`` insert-or-detect (T010): unique (type, dedup_key) in the producer's transaction, so
concurrent duplicates serialize on the key and exactly one event is stored."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.modules.events.models import DedupKey


async def claim(
    session: AsyncSession, event_type: str, key: str, event_id: UUID, now: datetime
) -> UUID | None:
    """Returns ``None`` when the key is new (claimed for ``event_id``), else the id of the existing event."""
    inserted = (
        await session.execute(
            insert(DedupKey)
            .values(type=event_type, dedup_key=key, event_id=event_id, first_seen_at=now)
            .on_conflict_do_nothing(index_elements=["type", "dedup_key"])
            .returning(DedupKey.event_id)
        )
    ).scalar_one_or_none()
    if inserted is not None:
        return None
    return (
        await session.execute(
            select(DedupKey.event_id).where(DedupKey.type == event_type, DedupKey.dedup_key == key)
        )
    ).scalar_one()
