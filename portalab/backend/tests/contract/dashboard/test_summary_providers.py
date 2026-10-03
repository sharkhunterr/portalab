"""009 T029 — the services change provider passes the summary contract kit."""

from datetime import timedelta
from uuid import uuid4

from portalab.capabilities.catalog import new_registry
from portalab.capabilities.health import SERVICE_DIRECTORY, SERVICE_STATE
from portalab.core.authz_port import Principal
from portalab.modules.dashboard.widgets.builtin import ServicesChanges, ServicesSummaryProvider
from tests.contract.dashboard.provider_kit import ChangeSummaryContractKit, SummaryWorld
from tests.integration.dashboard.conftest import FakeDirectory, FakeHealth
from tests.integration.privacy.conftest import NOW

ALLOWED = Principal(user_id=uuid4())
DENIED = Principal(user_id=uuid4())


class Authorizer:
    async def is_allowed(self, principal: Principal, permission: str, resource: object = None) -> bool:
        return principal is ALLOWED and permission == "services.read"


class TestServicesChanges(ChangeSummaryContractKit):
    async def make_world(self) -> SummaryWorld:
        capabilities = new_registry()
        capabilities.provide(SERVICE_STATE, FakeHealth(), instance_ref="t", owner="module:health")
        capabilities.provide(SERVICE_DIRECTORY, FakeDirectory(), instance_ref="t", owner="module:connectors")
        provider = ServicesChanges(ServicesSummaryProvider(capabilities, Authorizer()))  # type: ignore[arg-type]
        return SummaryWorld(provider, ALLOWED, DENIED, NOW - timedelta(days=30))
