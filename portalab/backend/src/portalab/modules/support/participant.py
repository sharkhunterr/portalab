"""Privacy participant (T036; R12): tickets, comments, attachments, drafts, diagnosis runs and feedback are
personal (``content``). Export lists the user's tickets and feedback; erasure tombstones the requester
(``NULL``), removes staff-only private fields, deletes attachments the user uploaded (blob and row), drafts
and diagnosis runs, and anonymizes authorship. Ticket histories stay (append-only), anonymized."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select, update

from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.core.blobstore import BlobStore
from portalab.core.db import Database
from portalab.modules.support.models import (
    Attachment,
    DiagnosisRun,
    FeedbackEvent,
    FeedbackItem,
    Ticket,
    TicketComment,
    TicketDraft,
    TicketHistory,
    TicketType,
)
from portalab.modules.support.workflow.types import parse_fields


class SupportParticipant:
    def __init__(self, database: Database, blobs: BlobStore | None) -> None:
        self.database = database
        self.blobs = blobs

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        async with self.database.session() as session:
            tickets = (
                (await session.execute(select(Ticket).where(Ticket.requester_id == user_id))).scalars().all()
            )
            feedback = (
                (await session.execute(select(FeedbackItem).where(FeedbackItem.submitter_id == user_id)))
                .scalars()
                .all()
            )
        records = [
            ExportRecord(
                "support.ticket",
                {
                    "number": t.number,
                    "title": t.title,
                    "state": t.state,
                    "created_at": t.created_at.isoformat(),
                },
            )
            for t in tickets
        ]
        records += [
            ExportRecord("support.feedback", {"kind": f.kind, "payload": f.payload, "status": f.status})
            for f in feedback
        ]
        return records

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        async with self.database.unit_of_work() as uow:
            session = uow.session
            uploads = (
                (await session.execute(select(Attachment).where(Attachment.uploaded_by == user_id)))
                .scalars()
                .all()
            )
            keys = [a.blob_key for a in uploads]
            await session.execute(delete(Attachment).where(Attachment.uploaded_by == user_id))
            for ticket in (
                (await session.execute(select(Ticket).where(Ticket.requester_id == user_id))).scalars().all()
            ):
                row = await session.get(TicketType, ticket.type_key)
                private = (
                    {d.key for d in parse_fields(row.fields) if d.visibility == "staff_only"}
                    if row
                    else set()
                )
                ticket.fields = {k: v for k, v in ticket.fields.items() if k not in private}
                ticket.requester_id = None
            await session.execute(
                update(Ticket).where(Ticket.assignee_id == user_id).values(assignee_id=None)
            )
            await session.execute(
                update(TicketComment).where(TicketComment.author_id == user_id).values(author_id=None)
            )
            await session.execute(
                update(TicketHistory).where(TicketHistory.actor_id == user_id).values(actor_id=None)
            )
            await session.execute(
                update(FeedbackItem).where(FeedbackItem.submitter_id == user_id).values(submitter_id=None)
            )
            await session.execute(
                update(FeedbackEvent).where(FeedbackEvent.actor_id == user_id).values(actor_id=None)
            )
            await session.execute(delete(TicketDraft).where(TicketDraft.user_id == user_id))
            await session.execute(delete(DiagnosisRun).where(DiagnosisRun.user_id == user_id))
        if self.blobs is not None:
            for key in keys:
                try:
                    await self.blobs.delete(key)
                except Exception:  # noqa: S112 — already gone
                    continue
