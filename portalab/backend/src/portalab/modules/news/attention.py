"""#336: the news' badge — the articles a member may read and has not opened yet, on « Headlines »."""

from collections.abc import Mapping

from portalab.core.authz_port import Principal
from portalab.modules.news.articles import ArticleService

ENTRY = "news.page"


class NewsAttention:
    def __init__(self, articles: ArticleService) -> None:
        self.articles = articles

    async def counts(self, principal: Principal) -> Mapping[str, int]:
        return {ENTRY: await self.articles.unread(principal)}
