"""Privacy participant (T003): media history, play/read activity (027), progress, sessions, account links
and requests are personal (``activity``) — exported and erased with the account; catalog objects and
community aggregates are not personal and stay (requests keep their catalog effect, the requester is
removed)."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select, update

from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.core.db import Database
from portalab.modules.media.insights.ingest import mark_days
from portalab.modules.media.models import (
    Activity,
    BookPosition,
    HistoryEntry,
    MediaObject,
    MediaRequest,
    PlaybackSession,
    QuotaLedger,
    QuotaUnits,
    RescueLedger,
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
            for activity in (
                await session.execute(
                    select(Activity).where(Activity.user_id == user_id).order_by(Activity.started_at)
                )
            ).scalars():
                records.append(
                    ExportRecord(
                        "media.activity",
                        {
                            "title": activity.title,
                            "series": activity.parent_title,
                            "kind": activity.kind,
                            "at": activity.started_at.isoformat(),
                            "seconds": round(activity.watched_s),
                            "progress": activity.progress,
                            "device": activity.device,
                            "platform": activity.platform,
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
            for rescue in (
                await session.execute(select(RescueLedger).where(RescueLedger.user_id == user_id))
            ).scalars():
                records.append(  # #57: rescues bought and titles saved
                    ExportRecord(
                        "media.rescue",
                        {
                            "reason": rescue.reason,
                            "delta": rescue.delta,
                            "title": rescue.title,
                            "at": rescue.created_at.isoformat(),
                        },
                    )
                )
            for book in (
                await session.execute(select(BookPosition).where(BookPosition.user_id == user_id))
            ).scalars():
                records.append(  # #20, #21: where I stopped listening or reading in the portal
                    ExportRecord(
                        "media.book_position",
                        {
                            "object": str(book.object_id),
                            "format": book.format,
                            "position": book.position,
                            "percent": book.percent,
                            "at": book.updated_at.isoformat(),
                        },
                    )
                )
        return records

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        async with self.database.unit_of_work() as uow:
            session = uow.session
            erased = (
                await session.execute(
                    delete(Activity).where(Activity.user_id == user_id).returning(Activity.started_at)
                )
            ).scalars()
            await mark_days(session, erased)
            for model in (
                HistoryEntry,
                UserProgress,
                PlaybackSession,
                UserLink,
                QuotaUnits,
                QuotaLedger,
                RescueLedger,
                BookPosition,
            ):
                await session.execute(delete(model).where(model.user_id == user_id))
            await session.execute(
                update(MediaRequest)
                .where(MediaRequest.requester_user_id == user_id)
                # 027: the account id on the request service goes too
                .values(requester_user_id=None, external_ref=MediaRequest.external_ref.op("-")("requester"))
            )
