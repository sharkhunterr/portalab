"""Privacy participant (T003; 020/021): export lists the member's own feed entries and Community visibility
choices; final deletion removes them and detaches the member from the events they organized (the events
stay — they belong to the community)."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select, update

from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.core.db import Database
from portalab.modules.community.models import CommunityEvent, FeedEntry, VisibilityPreference


class CommunityParticipant:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        async with self.database.session() as session:
            entries = list(
                (
                    await session.execute(
                        select(FeedEntry)
                        .where(FeedEntry.actor_user_id == user_id)
                        .order_by(FeedEntry.occurred_at)
                    )
                ).scalars()
            )
            preferences = list(
                (
                    await session.execute(
                        select(VisibilityPreference).where(VisibilityPreference.user_id == user_id)
                    )
                ).scalars()
            )
        records = [
            ExportRecord(
                "community.feed_entry",
                {"kind": e.kind, "params": dict(e.params), "occurred_at": e.occurred_at.isoformat()},
            )
            for e in entries
        ]
        records += [
            ExportRecord("community.visibility", {"datum_class": p.datum_class, "level": p.level})
            for p in preferences
        ]
        return records

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(delete(FeedEntry).where(FeedEntry.actor_user_id == user_id))
            await uow.session.execute(
                delete(VisibilityPreference).where(VisibilityPreference.user_id == user_id)
            )
            await uow.session.execute(
                update(CommunityEvent).where(CommunityEvent.organizer_id == user_id).values(organizer_id=None)
            )
