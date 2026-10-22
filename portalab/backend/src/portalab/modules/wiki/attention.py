"""#98: the wiki's badge — the drafts waiting to be published, for those who publish."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select

from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.modules.wiki.models import Page
from portalab.modules.wiki.permissions import WIKI_PUBLISH

ENTRY = "wiki.admin"


class DraftsAttention:
    def __init__(self, database: Database, authorizer: Authorizer) -> None:
        self.database = database
        self.authorizer = authorizer

    async def counts(self, principal: Principal) -> Mapping[str, int]:
        if not await self.authorizer.is_allowed(principal, WIKI_PUBLISH):
            return {}
        async with self.database.session() as session:
            drafts: Any = await session.scalar(select(func.count()).where(Page.status == "draft"))
        return {ENTRY: int(drafts or 0)}
