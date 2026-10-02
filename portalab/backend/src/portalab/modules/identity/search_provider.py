"""Users directory search provider (spec 008 T015, delivered by its owner through the search SDK): active
accounts matched on their display name, for principals holding ``users.read``. Only what the profile
view already shows to such a principal (the display name) is returned or matched — never the login, the
e-mail or private profile fields (FR-016)."""

import time
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.search import (
    FacetDef,
    ParsedQuery,
    ProviderResult,
    SearchItem,
    SearchRegistry,
    default_search,
)
from portalab.capabilities.search.fts import decode_cursor, encode_cursor, snippet, text_match, text_rank
from portalab.core.authz_port import Principal
from portalab.modules.identity.context import OWNER, IdentityContext
from portalab.modules.identity.domain.state_machine import AccountState
from portalab.modules.identity.models import User

USERS_READ = "users.read"


class UsersSearchProvider:
    kind = "users"
    label_key = "search.kind.users"
    required_permission = USERS_READ

    def __init__(self, ctx: IdentityContext) -> None:
        self.ctx = ctx

    def facets(self) -> Sequence[FacetDef]:
        return ()

    def _item(self, user_id: UUID, name: str, query: ParsedQuery, score: float = 0.0) -> SearchItem:
        return SearchItem(
            kind=self.kind,
            id=str(user_id),
            title=name,
            url_ref=f"/users/{user_id}",
            snippet=snippet(name, query.terms),
            score=score,
        )

    async def search(
        self, query: ParsedQuery, principal: Principal, ctx: LocaleContext, *, limit: int, cursor: str | None
    ) -> ProviderResult:
        started = time.perf_counter()
        if not query.normalized or not await self.ctx.authorizer.is_allowed(principal, USERS_READ):
            return ProviderResult()
        offset = decode_cursor(cursor)
        rank = text_rank([User.display_name], query).label("rank")
        stmt = (
            select(User.id, User.display_name, rank)
            .where(
                User.state == AccountState.ACTIVE.value,
                User.display_name.is_not(None),
                text_match([User.display_name], query),
            )
            .order_by(rank.desc(), func.lower(User.display_name), User.id)
            .offset(offset)
            .limit(limit + 1)
        )
        async with self.ctx.database.session() as session:
            rows = (await session.execute(stmt)).all()
        items = [self._item(row.id, row.display_name, query, float(row.rank)) for row in rows[:limit]]
        return ProviderResult(
            items=items,
            next_cursor=encode_cursor(offset + limit) if len(rows) > limit else None,
            took_ms=int((time.perf_counter() - started) * 1000),
        )

    async def hydrate(self, ids: Sequence[str], principal: Principal) -> Sequence[SearchItem]:
        if not await self.ctx.authorizer.is_allowed(principal, USERS_READ):
            return []
        wanted: list[UUID] = []
        for value in ids:
            try:
                wanted.append(UUID(value))
            except ValueError:
                continue
        async with self.ctx.database.session() as session:
            rows = (
                await session.execute(
                    select(User.id, User.display_name).where(
                        User.id.in_(wanted),
                        User.state == AccountState.ACTIVE.value,
                        User.display_name.is_not(None),
                    )
                )
            ).all()
        empty = ParsedQuery(text="", normalized="", terms=())
        return [self._item(row.id, row.display_name, empty) for row in rows]


def register_search(ctx: IdentityContext, registry: SearchRegistry = default_search) -> None:
    registry.register(UsersSearchProvider(ctx), owner=OWNER)
