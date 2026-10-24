"""017 / 008 FR-012 (#84) — ``SearchProvider(kind="statistics")`` passes the conformance kit (permission at
source, a retired statistic gone at once, plain snippets, limits); a statistic is found by its title and
description in the member's language, and one whose permission the member lacks is never found."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

import pytest

from portalab.capabilities.i18n import RENDERER, LocaleContext
from portalab.capabilities.search.testkit import ProviderWorld, SearchProviderContractKit, query
from portalab.core.authz_port import Principal
from portalab.modules.statistics.search import StatisticsSearchProvider
from tests.authz_fixtures import insert_user
from tests.integration.statistics.conftest import StatsHarness

pytestmark = pytest.mark.integration

FINISHED = {
    "key": "media.my_minutes",
    "title_key": "media:stat.my_minutes.title",
    "description_key": "media:stat.my_minutes.description",
    "domain": "media",
    "scope": "personal",
    "event_types": ["media.played"],
    "measure": {"kind": "sum", "field": "minutes"},
}
CATALOG = {
    ("media", "stat.my_minutes.title"): {"en": "Time I watched", "fr": "Mon temps de visionnage"},
    ("media", "stat.my_minutes.description"): {
        "en": "Minutes played, per day.",
        "fr": "Minutes vues, par jour.",
    },
    ("support", "stat.queue.title"): {"en": "Tickets waiting", "fr": "Tickets en attente"},
}


class Renderer:
    def t(
        self, key: str, ctx: LocaleContext, args: Mapping[str, Any] | None = None, *, namespace: str = "core"
    ) -> str:
        return CATALOG.get((namespace, key), {}).get(ctx.language, key)


class OnlyFor:
    def __init__(self, allowed: Principal) -> None:
        self.allowed = allowed

    async def is_allowed(self, principal: Principal, permission: str, resource: object = None) -> bool:
        return principal == self.allowed and permission == "statistics.read"


async def member(stats: StatsHarness) -> Principal:
    user: UUID = await insert_user(stats.database)
    return Principal(user_id=user)


class TestStatisticsProvider(SearchProviderContractKit):
    @pytest.fixture(autouse=True)
    def _harness(self, stats: StatsHarness) -> None:
        self.stats = stats

    async def make_world(self) -> ProviderWorld:
        await self.stats.define(FINISHED)
        allowed, denied = await member(self.stats), await member(self.stats)
        module = self.stats.module
        provider = StatisticsSearchProvider(module.provider, OnlyFor(allowed), module.capabilities)

        async def hide(key: str) -> None:
            await module.definitions.retire(Principal(channel="system"), key)

        return ProviderWorld(provider, allowed, denied, "minutes", hide)  # the keys, without i18n


async def test_found_in_the_members_language_within_their_permissions(stats: StatsHarness) -> None:
    stats.module.capabilities.provide(RENDERER, Renderer(), instance_ref="test", owner="module:i18n")
    await stats.define(FINISHED)
    await stats.define(
        {
            **FINISHED,
            "key": "support.queue",
            "title_key": "support:stat.queue.title",
            "description_key": None,
            "domain": "support",
            "scope": "global",
            "required_permission": "tickets.manage",
        }
    )
    provider = stats.search.provider("statistics")
    assert isinstance(provider, StatisticsSearchProvider)  # the module registers it
    viewer = await member(stats)

    async def found(text: str, language: str) -> list[tuple[str, str]]:
        ctx = LocaleContext(language=language)
        result = await provider.search(query(text), viewer, ctx, limit=10, cursor=None)
        return [(item.id, item.title) for item in result.items]

    assert await found("visionnage", "fr") == [("media.my_minutes", "Mon temps de visionnage")]
    assert await found("minutes per day", "en") == [("media.my_minutes", "Time I watched")]
    assert await found("tickets", "en") == []  # tickets.manage only: not in this member's catalog
    assert await found("watched", "fr") == []  # matched in the member's language, not another one
