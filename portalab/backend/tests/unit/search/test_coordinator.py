"""008 T005/T022 — parallel fan-out; a slow provider times out into an ``unavailable`` group and an
exception stays isolated; stable group order; caps; ungranted kinds absent (not even a group); filters
only reach providers that declare them; semantic candidates are re-hydrated and unknown ids dropped."""

import time
from collections.abc import Mapping, Sequence

import pytest

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.search import FacetDef, ParsedQuery, SearchRegistry
from portalab.core.authz_port import Principal
from portalab.modules.search.coordinator.coordinator import SearchCoordinator
from portalab.modules.search.parser.parser import InvalidFilter
from portalab.modules.search.settings import SearchConfig
from tests.unit.search.fakes import FakeAuthorizer, FakeProvider

ME = Principal(user_id=None)


def query(text: str = "", **kw: object) -> ParsedQuery:
    return ParsedQuery(text=text, normalized=text, terms=tuple(text.split()), **kw)  # type: ignore[arg-type]


def coordinator(*providers: FakeProvider, allowed: set[str] | None = None, **kw: object) -> SearchCoordinator:
    registry = SearchRegistry()
    for provider in providers:
        registry.register(provider, owner="module:test")
    config = SearchConfig(provider_timeout_ms=200, max_results_per_group=1, semantic_enabled=True)
    return SearchCoordinator(registry, FakeAuthorizer(allowed), lambda: config, **kw)  # type: ignore[arg-type]


async def test_isolation_timeouts_and_order() -> None:
    failures: list[tuple[str, str]] = []

    async def hook(kind: str, reason: str) -> None:
        failures.append((kind, reason))

    c = coordinator(
        FakeProvider("b_slow", delay=1.0),
        FakeProvider("a_ok"),
        FakeProvider("c_fail", fail=True),
        on_failure=hook,
    )
    started = time.perf_counter()
    outcome = await c.search(query("a"), ME, LocaleContext())
    assert time.perf_counter() - started < 0.8  # parallel, bounded by the budget
    assert [(g.kind, g.state) for g in outcome.groups] == [
        ("a_ok", "ok"),
        ("b_slow", "unavailable"),
        ("c_fail", "unavailable"),
    ]
    assert len(outcome.groups[0].items) == 1  # capped per group
    assert sorted(failures) == [("b_slow", "timeout"), ("c_fail", "error")]


async def test_ungranted_kinds_contribute_nothing() -> None:
    secret = FakeProvider("tickets", permission="tickets.read")
    c = coordinator(FakeProvider("wiki"), secret)
    outcome = await c.search(query("a"), ME, LocaleContext())
    assert [g.kind for g in outcome.groups] == ["wiki"] and secret.calls == 0
    only_secret = await c.search(query("a", kinds=("tickets",)), ME, LocaleContext())
    assert only_secret.groups == [] and only_secret.total == 0


async def test_filters_route_to_declaring_providers() -> None:
    stateful = FakeProvider("services", facets=(FacetDef("state", "x", values=("on", "off")),))
    c = coordinator(stateful, FakeProvider("wiki"))
    outcome = await c.search(query("a", filters={"state": ("on",)}), ME, LocaleContext())
    assert [g.kind for g in outcome.groups] == ["services"]
    with pytest.raises(InvalidFilter):
        await c.search(query("a", filters={"state": ("maybe",)}), ME, LocaleContext())
    with pytest.raises(InvalidFilter):
        await c.search(query("a", filters={"colour": ("red",)}), ME, LocaleContext())


async def test_semantic_rehydrates_and_drops_unknown() -> None:
    async def candidates(q: ParsedQuery, kinds: Sequence[str], k: int) -> Mapping[str, Sequence[str]]:
        return {"wiki": ["1", "999"]}

    async def available() -> bool:
        return True

    wiki = FakeProvider("wiki", titles=("alpha", "semantic neighbour"))
    registry = SearchRegistry()
    registry.register(wiki, owner="module:test")
    config = SearchConfig(max_results_per_group=5, semantic_enabled=True)
    c = SearchCoordinator(
        registry, FakeAuthorizer(), lambda: config, semantic=candidates, semantic_available=available
    )
    outcome = await c.search(query("alpha"), ME, LocaleContext())
    items = outcome.groups[0].items
    assert outcome.semantic == "ok"
    assert [(i.id, i.matched_by) for i in items] == [("0", "exact"), ("1", "semantic")]  # 999 dropped
    exact = await c.search(query("alpha", mode="exact"), ME, LocaleContext())
    assert exact.semantic == "off" and len(exact.groups[0].items) == 1


async def test_semantic_unavailable_is_reported() -> None:
    c = coordinator(FakeProvider("wiki"))
    outcome = await c.search(query("a", mode="semantic"), ME, LocaleContext())
    assert outcome.semantic == "unavailable" and outcome.groups[0].state == "ok"  # lexical continues
