"""Attachments (T023, T038; R5, OQ-77 default): uses the shared ``core.uploads`` helper — type from magic
bytes against ``support.attachments.allowedTypes``, size ≤ ``maxBytes``, at most ``maxPerPost`` per post,
images re-encoded (EXIF stripped), file names sanitized — then the optional ``support.attachment_scanner``.
Only images are served inline; everything else downloads (``Content-Disposition: attachment``, ``nosniff``).
Readers must be able to read the ticket; private (staff) attachments are staff-only."""

import asyncio
import hashlib
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.support import SCANNER
from portalab.core.authz_port import Principal
from portalab.core.blobstore import BlobStore
from portalab.core.errors import Forbidden, NotFound, ValidationFailed
from portalab.core.time import utc_now
from portalab.core.uploads import IMAGE_TYPES, UnsafeUpload, clean_upload
from portalab.modules.support.models import Attachment, Ticket
from portalab.modules.support.settings import SupportConfig
from portalab.modules.support.tickets.service import TicketService


class AttachmentRejected(ValidationFailed):
    default_code = "attachment.rejected"
    default_title = "This file cannot be attached"


class AttachmentNotFound(NotFound):
    default_code = "attachment.not_found"
    default_title = "Attachment not found"


@dataclass(frozen=True, slots=True)
class AttachmentFile:
    data: bytes
    content_type: str
    filename: str
    inline: bool


class AttachmentService:
    def __init__(
        self, tickets: TicketService, blobs: BlobStore | None, capabilities: CapabilityRegistry, config: Any
    ) -> None:
        self.tickets = tickets
        self.blobs = blobs
        self.capabilities = capabilities
        self.config = config  # callable → SupportConfig

    def _scanner(self) -> Any | None:
        try:
            providers = self.capabilities.system_providers(SCANNER)
        except Exception:
            return None
        return providers[0].provider if providers else None

    async def upload(
        self,
        principal: Principal,
        ticket_id: UUID,
        data: bytes,
        filename: str,
        *,
        comment_id: UUID | None = None,
        private: bool = False,
    ) -> Attachment:
        config: SupportConfig = self.config()
        if self.blobs is None:
            raise AttachmentRejected("Attachments are not available.", extensions={"reason": "unavailable"})
        database = self.tickets.database
        async with database.session() as session:
            ticket, roles = await self.tickets._load(session, ticket_id, principal)
            if private and "staff" not in roles:
                raise Forbidden("Only support staff add private attachments.")
            count = int(
                await session.scalar(
                    select(func.count()).where(
                        Attachment.ticket_id == ticket.id,
                        Attachment.comment_id.is_(None)
                        if comment_id is None
                        else Attachment.comment_id == comment_id,
                    )
                )
                or 0
            )
        if count >= config.attachments_max_per_post:
            raise AttachmentRejected("Too many files on this post.", extensions={"reason": "too_many"})
        allowed = frozenset(config.attachments_allowed_types)
        try:
            clean = await asyncio.to_thread(  # #274: decoded off the event loop
                clean_upload, data, filename, allowed=allowed, max_bytes=config.attachments_max_bytes
            )
        except UnsafeUpload as exc:
            raise AttachmentRejected(
                "This file type or size is not accepted.", extensions={"reason": exc.reason}
            ) from exc
        scanner = self._scanner()
        if scanner is not None:
            try:
                verdict = await asyncio.wait_for(scanner.scan(clean.data, clean.content_type), timeout=30)
            except Exception as exc:
                raise AttachmentRejected(
                    "The file could not be checked.", extensions={"reason": "scan_failed"}
                ) from exc
            if not verdict.clean:
                raise AttachmentRejected(
                    "The file was refused by the scanner.", extensions={"reason": "scanner"}
                )
        stored = await self.blobs.put("support", clean.data, content_type=clean.content_type)
        async with database.unit_of_work() as uow:
            session = uow.session
            locked, _ = await self.tickets._load(session, ticket_id, principal, lock=True)
            row = Attachment(
                ticket_id=locked.id,
                comment_id=comment_id,
                uploaded_by=self.tickets.user_of(principal),
                blob_key=stored.key,
                filename=clean.filename,
                content_type=clean.content_type,
                size=len(clean.data),
                sha256=hashlib.sha256(clean.data).hexdigest(),
                private=private,
                created_at=utc_now(self.tickets.clock),
            )
            session.add(row)
            await session.flush()
            locked.version, locked.updated_at = locked.version + 1, utc_now(self.tickets.clock)
            seq = await self.tickets._history(
                session,
                locked,
                "attachment_added",
                principal,
                {"attachment": str(row.id), "private": private},
            )
            await self.tickets._event(session, locked, "ticket.updated", seq)
            return row

    async def read(self, principal: Principal, attachment_id: UUID) -> AttachmentFile:
        async with self.tickets.database.session() as session:
            row = await session.get(Attachment, attachment_id)
            if row is None or self.blobs is None:
                raise AttachmentNotFound("This file does not exist.")
            try:
                _, roles = await self.tickets._load(session, row.ticket_id, principal)
            except NotFound as exc:
                raise AttachmentNotFound("This file does not exist.") from exc
        if row.private and "staff" not in roles:
            raise AttachmentNotFound("This file does not exist.")
        data = await self.blobs.get(row.blob_key)
        return AttachmentFile(data, row.content_type, row.filename, row.content_type in IMAGE_TYPES)

    async def purge_ticket(self, ticket: Ticket) -> None:
        if self.blobs is None:
            return
        async with self.tickets.database.session() as session:
            keys = [
                r[0]
                for r in await session.execute(
                    select(Attachment.blob_key).where(Attachment.ticket_id == ticket.id)
                )
            ]
        for key in keys:
            try:
                await self.blobs.delete(key)
            except Exception:  # noqa: S112 — a missing blob is already gone
                continue
