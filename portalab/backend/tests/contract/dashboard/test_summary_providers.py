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


async def test_service_links_give_each_service_its_state_and_address() -> None:
    """027 — the quick-access widget: each configured service, its state, and where to open it (its public
    address; without one, its status page)."""
    from portalab.capabilities.health import ServiceInfo
    from portalab.capabilities.i18n import LocaleContext
    from portalab.modules.dashboard.widgets.builtin import ServiceLinksProvider

    class Directory(FakeDirectory):
        async def services(self) -> list[ServiceInfo]:
            return [
                ServiceInfo(
                    id="s1", name="Media", connector="plex", state="enabled", link="https://plex.lan"
                ),
                ServiceInfo(id="s2", name="Books", connector="kavita", state="enabled"),
                ServiceInfo(id="s3", name="Gone", connector="kavita", state="disconnected"),
            ]

    capabilities = new_registry()
    capabilities.provide(SERVICE_STATE, FakeHealth(), instance_ref="t", owner="module:health")
    capabilities.provide(SERVICE_DIRECTORY, Directory(), instance_ref="t", owner="module:connectors")
    loaded = await ServiceLinksProvider(capabilities, Authorizer()).load(ALLOWED, {}, LocaleContext())  # type: ignore[arg-type]
    assert [(i["name"], i["state"], i["link"], i["route"]) for i in loaded.data["items"]] == [
        ("Media", "operational", "https://plex.lan", "/services/s1"),
        ("Books", "unavailable", None, "/services/s2"),
    ]


async def test_a_switched_off_service_is_not_watched() -> None:
    """A service an administrator switched off is not watched: the services widget neither counts it as
    unknown nor says « a source did not answer », and its quick link goes."""
    from portalab.capabilities.health import ServiceInfo
    from portalab.capabilities.i18n import LocaleContext
    from portalab.modules.dashboard.widgets.builtin import ServiceLinksProvider

    class Directory(FakeDirectory):
        async def services(self) -> list[ServiceInfo]:
            return [
                *await super().services(),
                ServiceInfo(id="s3", name="Search", connector="searxng", state="disabled"),
                ServiceInfo(id="s4", name="New", connector="plex", state="configured"),
            ]

    capabilities = new_registry()
    capabilities.provide(SERVICE_STATE, FakeHealth(), instance_ref="t", owner="module:health")
    capabilities.provide(SERVICE_DIRECTORY, Directory(), instance_ref="t", owner="module:connectors")
    summary = await ServicesSummaryProvider(capabilities, Authorizer()).load(ALLOWED, {}, LocaleContext())  # type: ignore[arg-type]
    assert summary.state == "available" and summary.partial_reasons == ()
    assert summary.data["total"] == 2 and "unknown" not in summary.data["counts"]
    links = await ServiceLinksProvider(capabilities, Authorizer()).load(ALLOWED, {}, LocaleContext())  # type: ignore[arg-type]
    assert [i["name"] for i in links.data["items"]] == ["Media", "Books"]
