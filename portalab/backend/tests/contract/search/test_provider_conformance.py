"""008 T006 — the first providers pass the reusable conformance kit (permission at source, immediate
visibility changes, plain-text snippets, limits, clean cancellation). Domain specs reuse the same kit."""

from dataclasses import replace
from uuid import uuid4

import pytest

from portalab.capabilities.health import SERVICE_DIRECTORY
from portalab.capabilities.navigation import NavigationContribution, NavigationRegistry
from portalab.capabilities.search.testkit import ProviderWorld, SearchProviderContractKit
from portalab.core.authz_port import Principal
from portalab.modules.identity.domain.state_machine import AccountState
from portalab.modules.identity.search_provider import UsersSearchProvider
from portalab.modules.search.providers.navigation import NavigationProvider
from portalab.modules.search.providers.services import ServicesProvider
from tests.integration.identity.helpers import set_state
from tests.integration.search.conftest import FakeDirectory, SearchHarness
from tests.unit.search.fakes import FakeAuthorizer

ALLOWED = Principal(user_id=uuid4())
DENIED = Principal(user_id=uuid4())


class PerPrincipal(FakeAuthorizer):
    def __init__(self, permission: str) -> None:
        super().__init__({permission})

    async def is_allowed(self, principal: Principal, permission: str, resource: object = None) -> bool:
        return principal is ALLOWED and permission in self.allowed


class TestServicesProvider(SearchProviderContractKit):
    async def make_world(self) -> ProviderWorld:
        from portalab.capabilities.catalog import new_registry

        capabilities = new_registry()
        capabilities.provide(SERVICE_DIRECTORY, FakeDirectory(), instance_ref="t", owner="module:connectors")
        return ProviderWorld(
            ServicesProvider(capabilities, PerPrincipal("services.read")), ALLOWED, DENIED, "jellyfin"
        )


class TestNavigationProvider(SearchProviderContractKit):
    async def make_world(self) -> ProviderWorld:
        from portalab.capabilities.catalog import new_registry

        navigation = NavigationRegistry()
        navigation.register(
            NavigationContribution(
                key="health.services",
                owner="module:health",
                kind="entry",
                label_key="Services",
                route="/services",
                required_permission="services.read",
            )
        )
        authorizer = PerPrincipal("services.read")
        return ProviderWorld(
            NavigationProvider(authorizer, new_registry(), navigation), ALLOWED, DENIED, "services"
        )


@pytest.mark.integration
class TestUsersProvider(SearchProviderContractKit):
    @pytest.fixture(autouse=True)
    def _harness(self, search: SearchHarness) -> None:
        self.harness = search

    async def make_world(self) -> ProviderWorld:
        from portalab.modules.identity.module import IdentityModule
        from tests.integration.identity.helpers import create_user

        identity = self.harness.full.identity
        module = IdentityModule(identity)
        await create_user(module, f"u{uuid4().hex[:8]}", display_name="Zoé Kit")
        provider = UsersSearchProvider(replace(identity, authorizer=PerPrincipal("users.read")))

        async def hide(user_id: str) -> None:
            from uuid import UUID

            await set_state(module, UUID(user_id), AccountState.SUSPENDED)

        return ProviderWorld(provider, ALLOWED, DENIED, "zoe", hide)
