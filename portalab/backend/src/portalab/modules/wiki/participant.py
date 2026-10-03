"""Privacy participant: wiki content is not personal except author references, tombstoned (``NULL``) on
erasure — revisions stay (the content belongs to the community knowledge base)."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select, update

from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.core.db import Database
from portalab.modules.wiki.models import Page, PageTranslation, Revision


class WikiParticipant:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        async with self.database.session() as session:
            rows = await session.execute(
                select(Revision.title, Revision.version, Revision.created_at).where(
                    Revision.author_id == user_id
                )
            )
            return [
                ExportRecord("wiki.revision", {"title": t, "version": v, "at": at.isoformat()})
                for t, v, at in rows
            ]

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                update(Revision).where(Revision.author_id == user_id).values(author_id=None)
            )
            await uow.session.execute(update(Page).where(Page.created_by == user_id).values(created_by=None))
            await uow.session.execute(
                update(PageTranslation).where(PageTranslation.updated_by == user_id).values(updated_by=None)
            )
