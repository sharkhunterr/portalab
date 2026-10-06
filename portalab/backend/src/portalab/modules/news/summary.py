"""« Since your last visit » for news (027): articles published since, that I may read."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select

from portalab.capabilities.dashboard import ChangeItem
from portalab.capabilities.i18n import LocaleContext
from portalab.core.authz_port import Principal
from portalab.modules.news.articles import ArticleService
from portalab.modules.news.models import Article


class NewsChanges:
    kind = "news"

    def __init__(self, articles: ArticleService) -> None:
        self.articles = articles

    async def changes_since(
        self, principal: Principal, since: datetime, limit: int, ctx: LocaleContext
    ) -> Sequence[ChangeItem]:
        async with self.articles.database.session() as session:
            rows = (
                (
                    await session.execute(
                        select(Article)
                        .where(Article.status == "published", Article.published_at > since)
                        .order_by(Article.published_at.desc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
        items = []
        for article in rows:
            if not await self.articles.readable(article, principal):
                continue
            items.append(
                ChangeItem(
                    kind="news",
                    occurred_at=article.published_at or since,
                    ref=f"/news/{article.slug}",
                    title=article.title,
                    detail=article.summary[:160] or None,
                    priority=3,
                )
            )
        return items
