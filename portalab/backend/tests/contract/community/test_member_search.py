"""012 T011 — ``SearchProvider(kind="member")`` passes the 008 conformance kit: permission at source,
member listing visibility honoured immediately (search and hydrate), plain-text snippets, limits."""

from uuid import UUID

import pytest

from portalab.capabilities.search.testkit import ProviderWorld, SearchProviderContractKit
from portalab.core.authz_port import Principal
from portalab.modules.community.discovery.providers import MemberSearchProvider
from tests.integration.community.conftest import CoHarness


class OnlyFor:
    def __init__(self, allowed: Principal) -> None:
        self.allowed = allowed

    async def is_allowed(self, principal: Principal, permission: str, resource: object = None) -> bool:
        return principal == self.allowed and permission == "community.read"


@pytest.mark.integration
class TestMemberProvider(SearchProviderContractKit):
    @pytest.fixture(autouse=True)
    def _harness(self, co: CoHarness) -> None:
        self.co = co

    async def make_world(self) -> ProviderWorld:
        allowed, denied = self.co.p("ulrich"), self.co.p("vera")
        provider = MemberSearchProvider(self.co.module.members, OnlyFor(allowed))
        names = {str(v): k for k, v in self.co.people.items()}

        async def hide(member: str) -> None:
            await self.co.prefer(names[str(UUID(member))], "member_listing", "private")

        return ProviderWorld(provider, allowed, denied, "s", hide)  # Boss, Ursula
