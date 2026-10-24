"""Gamification search provider (spec 008 FR-012, #84): the achievements to earn and the quests open now,
for principals holding ``gamification.read`` — matched on their label and description, as the catalogs show
them. A hidden achievement stays hidden: it is only found by a member who has unlocked it (never its name
or description otherwise, FR-016). Filterable by type (``achievement`` / ``quest``)."""

import time
from collections.abc import Sequence
from dataclasses import replace
from uuid import UUID

from portalab.capabilities.i18n import LocaleContext, normalize_for_search
from portalab.capabilities.search import FacetDef, ParsedQuery, ProviderResult, SearchItem
from portalab.capabilities.search.fts import decode_cursor, encode_cursor, snippet
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.time import Clock, utc_now
from portalab.modules.gamification.achievements.evaluator import Achievements
from portalab.modules.gamification.permissions import READ
from portalab.modules.gamification.quests.service import Quests


class GamificationSearchProvider:
    kind = "gamification"
    label_key = "search.kind.gamification"
    required_permission = READ

    def __init__(
        self,
        achievements: Achievements,
        quests: Quests,
        authorizer: Authorizer,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.achievements = achievements
        self.quests = quests
        self.authorizer = authorizer
        self.clock = clock

    def facets(self) -> Sequence[FacetDef]:
        return (FacetDef("type", "search.facet.type", values=("achievement", "quest")),)

    async def _unlocked(self, user: UUID | None) -> set[str]:
        if user is None:
            return set()
        async with self.achievements.database.session() as session:
            return await self.achievements.unlocked(session, user)

    async def _entries(self, principal: Principal) -> list[tuple[SearchItem, str]]:
        """Every achievement and open quest the principal may know of, with its description."""
        if not await self.authorizer.is_allowed(principal, READ):
            return []  # scoped at source too, not only by the coordinator
        now = utc_now(self.clock)
        unlocked = await self._unlocked(principal.acting_for or principal.user_id)
        out: list[tuple[SearchItem, str]] = []
        for achievement in await self.achievements.definitions(now):
            definition = achievement.definition
            if definition.hidden and achievement.key not in unlocked:
                continue
            state = "unlocked" if achievement.key in unlocked else "locked"
            item = SearchItem(
                kind=self.kind,
                id=f"achievement:{achievement.key}",
                title=definition.label,
                url_ref=f"/community/achievements#{achievement.key}",
                facets={"type": "achievement", "state": state, "category": definition.category},
            )
            out.append((item, definition.description))
        for quest in await self.quests.definitions(now):
            if quest.open_at(now):
                item = SearchItem(
                    kind=self.kind,
                    id=f"quest:{quest.key}",
                    title=quest.definition.label,
                    url_ref=f"/community/quests#{quest.key}",
                    facets={"type": "quest", "subtype": quest.definition.kind},
                )
                out.append((item, quest.definition.description))
        return out

    async def search(
        self, query: ParsedQuery, principal: Principal, ctx: LocaleContext, *, limit: int, cursor: str | None
    ) -> ProviderResult:
        started = time.perf_counter()
        if not query.terms:
            return ProviderResult()
        wanted = query.filters.get("type")
        matches: list[SearchItem] = []
        for item, description in await self._entries(principal):
            if wanted and item.facets["type"] not in wanted:
                continue
            haystack = normalize_for_search(f"{item.title} {description}", ctx.language)
            if all(term in haystack for term in query.terms):
                matches.append(replace(item, snippet=snippet(description or item.title, query.terms)))
        counts: dict[str, int] = {}
        for item in matches:
            counts[item.facets["type"]] = counts.get(item.facets["type"], 0) + 1
        offset = decode_cursor(cursor)
        return ProviderResult(
            items=matches[offset : offset + limit],
            next_cursor=encode_cursor(offset + limit) if offset + limit < len(matches) else None,
            facets={"type": counts},
            took_ms=int((time.perf_counter() - started) * 1000),
        )

    async def hydrate(self, ids: Sequence[str], principal: Principal) -> Sequence[SearchItem]:
        wanted = set(ids)
        return [item for item, _ in await self._entries(principal) if item.id in wanted]
