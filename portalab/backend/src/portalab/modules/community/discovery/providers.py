"""Member search (T012; US8): ``SearchProvider(kind="member")`` for 008 — active members matched on their
display name, scoped **at source** by ``community.read`` and each member's ``member_listing`` visibility
(listing surface). Only the display name is matched or returned."""

import time
from collections.abc import Sequence
from uuid import UUID

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.search import FacetDef, ParsedQuery, ProviderResult, SearchItem
from portalab.capabilities.search.fts import decode_cursor, encode_cursor, snippet
from portalab.core.authz_port import Authorizer, Principal
from portalab.modules.community.members.service import Members
from portalab.modules.community.permissions import READ


class MemberSearchProvider:
    kind = "member"
    label_key = "community:search.member"
    required_permission = READ

    def __init__(self, members: Members, authorizer: Authorizer) -> None:
        self.members = members
        self.authorizer = authorizer

    def facets(self) -> Sequence[FacetDef]:
        return ()

    def _item(self, member: UUID, name: str, query: ParsedQuery) -> SearchItem:
        return SearchItem(
            kind=self.kind,
            id=str(member),
            title=name,
            url_ref=f"/community/members/{member}",
            snippet=snippet(name, query.terms),
        )

    async def search(
        self, query: ParsedQuery, principal: Principal, ctx: LocaleContext, *, limit: int, cursor: str | None
    ) -> ProviderResult:
        started = time.perf_counter()
        if not query.normalized or not await self.authorizer.is_allowed(principal, READ):
            return ProviderResult()
        page = await self.members.page(principal, query=query.text, offset=decode_cursor(cursor), limit=limit)
        return ProviderResult(
            items=[self._item(m.id, m.display_name, query) for m in page.items],
            next_cursor=encode_cursor(page.next_offset) if page.next_offset is not None else None,
            took_ms=int((time.perf_counter() - started) * 1000),
        )

    async def hydrate(self, ids: Sequence[str], principal: Principal) -> Sequence[SearchItem]:
        if not await self.authorizer.is_allowed(principal, READ):
            return []
        empty = ParsedQuery(text="", normalized="", terms=())
        out: list[SearchItem] = []
        for value in ids:
            try:
                member = UUID(value)
            except ValueError:
                continue
            found = await self.members.get(principal, member)
            if found is not None and found[1]:
                out.append(self._item(member, found[0], empty))
        return out
