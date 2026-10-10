"""Privacy participant: articles are not personal; author references are tombstoned on erasure; what a
member read (#48) is exported with their data and erased with them."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select, update

from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.core.db import Database
from portalab.modules.news.models import Article, ArticleRead, ArticleRevision


class NewsParticipant:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        async with self.database.session() as session:
            rows = await session.execute(
                select(Article.title, Article.status).where(Article.author_id == user_id)
            )
            records = [ExportRecord("news.article", {"title": t, "status": s}) for t, s in rows]
            reads = await session.execute(
                select(Article.title, ArticleRead.read_at)
                .join(Article, Article.id == ArticleRead.article_id)
                .where(ArticleRead.user_id == user_id)
            )
            records += [ExportRecord("news.read", {"title": t, "read_at": at.isoformat()}) for t, at in reads]
            return records

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                update(Article).where(Article.author_id == user_id).values(author_id=None)
            )
            await uow.session.execute(delete(ArticleRead).where(ArticleRead.user_id == user_id))
            await uow.session.execute(
                update(ArticleRevision).where(ArticleRevision.author_id == user_id).values(author_id=None)
            )
