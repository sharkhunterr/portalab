"""013 / 008 FR-012 (#84) — ``SearchProvider(kind="gamification")`` passes the conformance kit (permission at
source, a retired achievement gone at once, plain snippets, limits) and keeps hidden achievements hidden: one
is found only by the member who unlocked it; open quests are found too, and the type filter tells them
apart."""

from datetime import timedelta

import pytest

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.search import ParsedQuery
from portalab.capabilities.search.testkit import ProviderWorld, SearchProviderContractKit, query
from portalab.core.authz_port import Principal
from portalab.modules.gamification.search import GamificationSearchProvider
from tests.integration.gamification.conftest import SYSTEM, GamHarness

pytestmark = pytest.mark.integration

OWL = {
    "label": "Night owl",
    "description": "Finish a film after midnight",
    "criteria": [{"kind": "level_at_least", "level": 5}],
}


class OnlyFor:
    def __init__(self, allowed: Principal) -> None:
        self.allowed = allowed

    async def is_allowed(self, principal: Principal, permission: str, resource: object = None) -> bool:
        return principal == self.allowed and permission == "gamification.read"


class TestGamificationProvider(SearchProviderContractKit):
    @pytest.fixture(autouse=True)
    def _harness(self, gm: GamHarness) -> None:
        self.gm = gm

    async def make_world(self) -> ProviderWorld:
        await self.gm.module.achievements.save(SYSTEM, "night_owl", OWL)
        self.gm.clock.advance(timedelta(seconds=1))
        allowed, denied = self.gm.p("ursula"), self.gm.p("ulrich")
        module = self.gm.module
        provider = GamificationSearchProvider(
            module.achievements, module.quests, OnlyFor(allowed), clock=self.gm.clock
        )

        async def hide(item: str) -> None:
            await module.achievements.retire(SYSTEM, item.removeprefix("achievement:"))

        return ProviderWorld(provider, allowed, denied, "owl", hide)


def search_for(text: str, kinds: tuple[str, ...] = ()) -> ParsedQuery:
    parsed = query(text)
    return ParsedQuery(parsed.text, parsed.normalized, parsed.terms, filters={"type": kinds} if kinds else {})


async def test_hidden_achievements_and_quests(gm: GamHarness) -> None:
    await gm.module.achievements.save(SYSTEM, "secret", {**OWL, "hidden": True})
    await gm.module.quests.save(
        SYSTEM,
        "owl_week",
        {
            "kind": "quest",
            "label": "Owl week",
            "description": "Seven late films",
            "steps": [{"kind": "event_count", "event_type": "media.played", "count": 7}],
        },
    )
    gm.clock.advance(timedelta(seconds=1))
    provider = gm.search.provider("gamification")
    assert isinstance(provider, GamificationSearchProvider)  # the module registers it
    ursula, ulrich = gm.p("ursula"), gm.p("ulrich")

    async def found(who: Principal, text: str, *kinds: str) -> set[str]:
        result = await provider.search(search_for(text, kinds), who, LocaleContext(), limit=10, cursor=None)
        return {item.id for item in result.items}

    assert await found(ursula, "owl") == {"quest:owl_week"}  # the hidden one is not even hinted at
    assert await found(ursula, "midnight") == set()  # nor through its description
    async with gm.database.unit_of_work() as uow:
        await gm.module.achievements.unlock_by_key(uow.session, gm.people["ulrich"], "secret", gm.clock.now())
    assert await found(ulrich, "owl") == {"achievement:secret", "quest:owl_week"}
    assert await found(ulrich, "owl", "quest") == {"quest:owl_week"}
    assert await found(ursula, "owl") == {"quest:owl_week"}  # still hidden for who has not earned it
    assert [i.id for i in await provider.hydrate(["achievement:secret"], ursula)] == []
    [owl] = await provider.hydrate(["achievement:secret"], ulrich)
    assert owl.title == "Night owl" and owl.facets["state"] == "unlocked"
