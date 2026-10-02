"""Test doubles for search providers, resolvers and the authorizer."""

import asyncio
from collections.abc import Sequence

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.search import FacetDef, ObjectRef, ParsedQuery, ProviderResult, SearchItem
from portalab.core.authz_port import Principal, ResourceRef


class FakeAuthorizer:
    def __init__(self, allowed: set[str] | None = None) -> None:
        self.allowed = allowed if allowed is not None else {"search.use"}

    async def is_allowed(
        self, principal: Principal, permission: str, resource: ResourceRef | None = None
    ) -> bool:
        return permission in self.allowed


class FakeProvider:
    label_key = "search.kind.fake"

    def __init__(
        self,
        kind: str,
        *,
        permission: str = "search.use",
        titles: Sequence[str] = ("alpha", "beta"),
        delay: float = 0.0,
        fail: bool = False,
        facets: Sequence[FacetDef] = (),
    ) -> None:
        self.kind = kind
        self.required_permission = permission
        self.titles = list(titles)
        self.delay = delay
        self.fail = fail
        self._facets = tuple(facets)
        self.calls = 0

    def facets(self) -> Sequence[FacetDef]:
        return self._facets

    def _item(self, index: int) -> SearchItem:
        return SearchItem(self.kind, str(index), self.titles[index], f"/{self.kind}/{index}")

    async def search(
        self, query: ParsedQuery, principal: Principal, ctx: LocaleContext, *, limit: int, cursor: str | None
    ) -> ProviderResult:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("boom")
        items = [self._item(i) for i, t in enumerate(self.titles) if not query.terms or query.terms[0] in t]
        return ProviderResult(items=items, facets={"state": {"on": len(items)}})

    async def hydrate(self, ids: Sequence[str], principal: Principal) -> Sequence[SearchItem]:
        return [self._item(int(i)) for i in ids if i.isdigit() and int(i) < len(self.titles)]


class FakeResolver:
    prefixes = ("#",)

    def __init__(self, kind: str, known: dict[str, str] | None = None) -> None:
        self.kind = kind
        self.known = known or {}

    async def resolve(self, ref: str, principal: Principal) -> ObjectRef | None:
        key = ref.removeprefix("#")
        return (
            ObjectRef(self.kind, key, self.known[key], f"/{self.kind}/{key}") if key in self.known else None
        )
