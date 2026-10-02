"""Template for a domain search provider (spec 008 T024) — copy into the *owning* module (never into
``modules/search``), rename, and prove it with ``SearchProviderContractKit`` (see docs/search-providers.md).

Rules: query your own tables only; apply the principal's permission and the domain's visibility rules
*inside* the query; return plain-text snippets (``snippet()``); ``hydrate`` re-checks access; never log
or emit the query text."""

import time
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.search import FacetDef, ParsedQuery, ProviderResult, SearchItem
from portalab.capabilities.search.fts import decode_cursor, encode_cursor, snippet, text_match, text_rank
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.db import Database


class TemplateProvider:  # pragma: no cover - documentation template
    kind = "example"  # plugins: "plugin:<key>"
    label_key = "search.kind.example"
    required_permission = "example.read"

    def __init__(self, database: Database, authorizer: Authorizer, model: type) -> None:
        self.database = database
        self.authorizer = authorizer
        self.model = model  # your ORM model with ``id``, ``title``, ``body`` columns

    def facets(self) -> Sequence[FacetDef]:
        return (FacetDef("status", "search.facet.status", values=("open", "closed")),)

    async def search(
        self, query: ParsedQuery, principal: Principal, ctx: LocaleContext, *, limit: int, cursor: str | None
    ) -> ProviderResult:
        started = time.perf_counter()
        if not await self.authorizer.is_allowed(principal, self.required_permission):
            return ProviderResult()
        m = self.model
        offset = decode_cursor(cursor)
        rank = text_rank([m.title], query).label("rank")  # type: ignore[attr-defined]
        stmt: Any = select(m, rank).where(text_match([m.title, m.body], query))  # type: ignore[attr-defined]
        # + the domain's visibility predicate for ``principal`` here (owner, audience, privacy level…)
        for name, values in query.filters.items():
            stmt = stmt.where(getattr(m, name).in_(values))
        stmt = stmt.order_by(rank.desc()).offset(offset).limit(limit + 1)
        async with self.database.session() as session:
            rows = (await session.execute(stmt)).all()
        items = [
            SearchItem(
                self.kind,
                str(row[0].id),
                row[0].title,
                f"/example/{row[0].id}",
                snippet=snippet(row[0].body, query.terms),
                score=float(row.rank),
            )
            for row in rows[:limit]
        ]
        return ProviderResult(
            items=items,
            next_cursor=encode_cursor(offset + limit) if len(rows) > limit else None,
            took_ms=int((time.perf_counter() - started) * 1000),
        )

    async def hydrate(self, ids: Sequence[str], principal: Principal) -> Sequence[SearchItem]:
        return []  # load ``ids`` with the same permission + visibility predicate; drop the rest
