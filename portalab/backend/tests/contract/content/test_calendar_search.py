"""011 / 008 FR-012 (#84) — ``SearchProvider(kind="calendar")`` passes the conformance kit (permission at
source, an archived publication gone at once, plain snippets, limits); its items come through the calendar
sources, so what a source keeps from a member — an article scheduled for later is for editors only — is
never found by them; the coming items first."""

from datetime import timedelta
from uuid import UUID

import pytest

from portalab.capabilities.i18n import LocaleContext
from portalab.capabilities.search.testkit import ProviderWorld, SearchProviderContractKit, query
from portalab.core.authz_port import Principal
from portalab.core.time import FixedClock, utc_now
from portalab.modules.calendar.search import CalendarSearchProvider
from portalab.modules.news.articles import ArticleInput
from tests.integration.content.conftest import ContentHarness

pytestmark = pytest.mark.integration


class OnlyFor:
    def __init__(self, allowed: Principal) -> None:
        self.allowed = allowed

    async def is_allowed(self, principal: Principal, permission: str, resource: object = None) -> bool:
        return principal == self.allowed and permission == "calendar.read"


async def article(ct: ContentHarness, title: str, *, in_days: int = 0) -> UUID:
    eddie = ct.p("eddie")
    row = await ct.news.articles.create(eddie, ArticleInput(title, "Come along", summary=title))
    if in_days:
        when = utc_now(ct.calendar.clock) + timedelta(days=in_days)
        await ct.news.articles.transition(eddie, row.id, "schedule", publish_at=when)
    else:
        await ct.news.articles.transition(eddie, row.id, "publish")
    return row.id


class TestCalendarProvider(SearchProviderContractKit):
    @pytest.fixture(autouse=True)
    def _harness(self, ct: ContentHarness, people: dict[str, UUID]) -> None:
        self.ct = ct

    async def make_world(self) -> ProviderWorld:
        await article(self.ct, "Movie night recap")
        allowed, denied = self.ct.p("rita"), self.ct.p("sam")
        calendar = self.ct.calendar
        provider = CalendarSearchProvider(
            calendar.aggregator, OnlyFor(allowed), lambda: calendar.config, clock=calendar.clock
        )

        async def hide(item: str) -> None:
            await self.ct.news.articles.transition(self.ct.p("eddie"), UUID(item.split(":", 1)[1]), "archive")

        return ProviderWorld(provider, allowed, denied, "movie night", hide)


async def test_sources_keep_their_audience(
    ct: ContentHarness, people: dict[str, UUID], clock: FixedClock
) -> None:
    await article(ct, "Halloween night recap")
    clock.advance(timedelta(hours=1))
    later = await article(ct, "Halloween night", in_days=3)
    provider = ct.search.provider("calendar")
    assert isinstance(provider, CalendarSearchProvider)  # the module registers it

    async def found(name: str) -> list[str]:
        result = await provider.search(query("halloween"), ct.p(name), LocaleContext(), limit=10, cursor=None)
        return [item.title for item in result.items]

    assert await found("rita") == ["Halloween night recap"]  # the scheduled one is for editors only
    assert await found("eddie") == ["Halloween night", "Halloween night recap"]  # what comes, first
    assert [i.id for i in await provider.hydrate([f"news:{later}"], ct.p("rita"))] == []
    [item] = await provider.hydrate([f"news:{later}"], ct.p("eddie"))
    assert item.url_ref.startswith("/news/") and item.facets["source"] == "news"
