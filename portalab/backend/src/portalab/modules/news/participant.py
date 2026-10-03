"""Privacy participant: articles are not personal; author references are tombstoned on erasure."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select, update

from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.core.db import Database
from portalab.modules.news.models import Article, ArticleRevision


class NewsParticipant:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        async with self.database.session() as session:
            rows = await session.execute(
                select(Article.title, Article.status).where(Article.author_id == user_id)
            )
            return [ExportRecord("news.article", {"title": t, "status": s}) for t, s in rows]

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                update(Article).where(Article.author_id == user_id).values(author_id=None)
            )
            await uow.session.execute(
                update(ArticleRevision).where(ArticleRevision.author_id == user_id).values(author_id=None)
            )
