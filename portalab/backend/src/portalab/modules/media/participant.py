"""Privacy participant (T003): media history, progress, sessions, account links and requests are personal
(``activity``) — exported and erased with the account; catalog objects and community aggregates are not
personal and stay (requests keep their catalog effect, the requester is removed)."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select, update

from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.core.db import Database
from portalab.modules.media.models import (
    HistoryEntry,
    MediaObject,
    MediaRequest,
    PlaybackSession,
    QuotaLedger,
    QuotaUnits,
    UserLink,
    UserProgress,
)


class MediaParticipant:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        records: list[ExportRecord] = []
        async with self.database.session() as session:
            for entry, obj in await session.execute(
                select(HistoryEntry, MediaObject)
                .join(MediaObject, MediaObject.id == HistoryEntry.object_id)
                .where(HistoryEntry.user_id == user_id, HistoryEntry.kind != "progress")
                .order_by(HistoryEntry.occurred_at)
            ):
                records.append(
                    ExportRecord(
                        "media.history",
                        {
                            "title": obj.title,
                            "kind": obj.kind,
                            "at": entry.occurred_at.isoformat(),
                            "finished": entry.completed,
                        },
                    )
                )
            for link in (
                await session.execute(select(UserLink).where(UserLink.user_id == user_id))
            ).scalars():
                records.append(
                    ExportRecord(
                        "media.link",
                        {
                            "service_id": str(link.service_id),
                            "account": link.external_user_id,
                            "verified": link.verified,
                        },
                    )
                )
            for request in (
                await session.execute(select(MediaRequest).where(MediaRequest.requester_user_id == user_id))
            ).scalars():
                records.append(
                    ExportRecord(
                        "media.request",
                        {
                            "title": request.external_ref.get("title"),
                            "state": request.state,
                            "requested_at": request.requested_at.isoformat(),
                        },
                    )
                )
        return records

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        async with self.database.unit_of_work() as uow:
            session = uow.session
            for model in (HistoryEntry, UserProgress, PlaybackSession, UserLink, QuotaUnits, QuotaLedger):
                await session.execute(delete(model).where(model.user_id == user_id))
            await session.execute(
                update(MediaRequest)
                .where(MediaRequest.requester_user_id == user_id)
                .values(requester_user_id=None)
            )
