"""#98: the shop's badges — the purchases waiting for an administrator's decision (a film in 4K with the
member's wishes, a service's access…), and the community projects waiting for one (to open their funding,
or to approve them once funded), each for those who may decide them; a member's own reserve, when
something came into it since they last opened it or a purchase waits there for its form (#303); and the
community projects added or moved on since they last opened them (#303)."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select

from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database
from portalab.modules.marketplace.models import MarketRequest, Ownership, Project
from portalab.modules.marketplace.openings.service import Openings
from portalab.modules.marketplace.permissions import MANAGE, PROJECTS_MANAGE
from portalab.modules.marketplace.projects.service import Projects

ENTRY = "marketplace.admin_requests"
PROJECTS = "marketplace.projects_admin"
RESERVE = "marketplace.reserve"
PROJECTS_NEW = "marketplace.projects"


class ShopAttention:
    def __init__(self, database: Database, authorizer: Authorizer) -> None:
        self.database = database
        self.authorizer = authorizer

    async def counts(self, principal: Principal) -> Mapping[str, int]:
        queries: dict[str, Any] = {}
        if await self.authorizer.is_allowed(principal, MANAGE):
            queries[ENTRY] = select(func.count()).where(MarketRequest.state == "pending")
        if await self.authorizer.is_allowed(principal, PROJECTS_MANAGE):
            # an idea is left out: every proposal of a project makes one, even before its moderation
            queries[PROJECTS] = select(func.count()).where(Project.state.in_(("proposal", "validation")))
        if not queries:
            return {}
        async with self.database.session() as session:
            return {key: int(await session.scalar(query) or 0) for key, query in queries.items()}


class ReserveAttention:
    def __init__(self, database: Database, openings: Openings, projects: Projects) -> None:
        self.database = database
        self.openings = openings
        self.projects = projects

    async def counts(self, principal: Principal) -> Mapping[str, int]:
        user = principal.acting_for or principal.user_id
        if user is None:
            return {}
        async with self.database.session() as session:
            # #303: a purchase waiting for its form (a project to name, a film to choose) waits in my reserve
            todo = await session.scalar(
                select(func.count()).where(
                    Ownership.user_id == user, Ownership.state == "needs_configuration"
                )
            )
        return {
            RESERVE: await self.openings.unseen(user) + int(todo or 0),
            PROJECTS_NEW: await self.projects.unseen(user),
        }
