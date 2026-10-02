"""Reusable ``SearchProvider`` conformance kit (spec 008 T006). Every provider — module or plugin — proves
the permission-at-source contract with::

    class TestWikiProvider(SearchProviderContractKit):
        async def make_world(self) -> ProviderWorld: ...   # provider, principals, a matching term, hide()

The kit checks that the provider scopes results by principal *inside* its own query (a principal without
access gets nothing, even when calling the provider directly), that a visibility change is effective on
the very next query and in ``hydrate``, that snippets are plain-text segments (no markup injected), that
``limit`` is honoured, and that a cancelled search (time budget) ends cleanly.
"""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.search import ParsedQuery, SearchProvider, Segment
from portalab.core.authz_port import Principal


@dataclass
class ProviderWorld:
    provider: SearchProvider
    allowed: Principal  # may see the matching item
    denied: Principal  # lacks the provider's permission (or the item's visibility)
    term: str  # matches at least one item visible to ``allowed``
    hide: Callable[[str], Awaitable[None]] | None = None  # make an item invisible to ``allowed``


def query(term: str) -> ParsedQuery:
    normalized = term.casefold()
    return ParsedQuery(text=term, normalized=normalized, terms=tuple(normalized.split()), mode="exact")


class SearchProviderContractKit:
    """Subclass and implement ``make_world``; every ``test_*`` runs against your provider."""

    ctx = LocaleContext()

    async def make_world(self) -> ProviderWorld:
        raise NotImplementedError

    async def test_principal_scoping_at_source(self) -> None:
        world = await self.make_world()
        allowed = await world.provider.search(
            query(world.term), world.allowed, self.ctx, limit=10, cursor=None
        )
        assert allowed.items, "the allowed principal must find the matching item"
        denied = await world.provider.search(query(world.term), world.denied, self.ctx, limit=10, cursor=None)
        assert list(denied.items) == [], "a principal without access must get nothing from the provider"
        assert all(sum(counts.values()) == 0 for counts in denied.facets.values())
        ids = [item.id for item in allowed.items]
        assert list(await world.provider.hydrate(ids, world.denied)) == []

    async def test_visibility_change_is_immediate(self) -> None:
        world = await self.make_world()
        if world.hide is None:
            return  # no per-item visibility in this provider (kind-level permission only)
        found = await world.provider.search(query(world.term), world.allowed, self.ctx, limit=10, cursor=None)
        target = found.items[0].id
        await world.hide(target)
        again = await world.provider.search(query(world.term), world.allowed, self.ctx, limit=10, cursor=None)
        assert target not in {item.id for item in again.items}
        assert target not in {item.id for item in await world.provider.hydrate([target], world.allowed)}

    async def test_snippets_are_plain_segments(self) -> None:
        world = await self.make_world()
        result = await world.provider.search(
            query(world.term), world.allowed, self.ctx, limit=10, cursor=None
        )
        for item in result.items:
            assert all(isinstance(segment, Segment) for segment in item.snippet)
            text = "".join(segment.text for segment in item.snippet)
            assert "<mark" not in text and "<em" not in text, "highlighting is structural, never markup"

    async def test_limit_is_honoured(self) -> None:
        world = await self.make_world()
        result = await world.provider.search(query(world.term), world.allowed, self.ctx, limit=1, cursor=None)
        assert len(result.items) <= 1

    async def test_cancellation_is_clean(self) -> None:
        world = await self.make_world()
        task = asyncio.ensure_future(
            world.provider.search(query(world.term), world.allowed, self.ctx, limit=10, cursor=None)
        )
        await asyncio.sleep(0)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        # the provider still works afterwards
        assert (
            await world.provider.search(query(world.term), world.allowed, self.ctx, limit=10, cursor=None)
        ).items
