"""023 T015 — the sample plugin contributes to every official extension point through its context;
contributions are namespaced and permission-gated; conflicts resolve deterministically and singular-point
losers are flagged in diagnostics; the author kit passes."""

import pytest

from portalab.capabilities.marketplace import ActivationResult, OwnershipView, ProductType
from portalab.modules.plugins.manifest.schema import EXTENSION_POINTS
from tests.contract.plugins.kit import check_contributions, check_guard, check_manifest, check_removal
from tests.integration.plugins.conftest import HELLO, SYSTEM, PlHarness

pytestmark = pytest.mark.integration
POINTS = set(EXTENSION_POINTS)


async def test_every_point(pl: PlHarness) -> None:
    check_manifest(HELLO)
    await pl.installed(pl.hello())
    await check_contributions(pl.module, "hello", POINTS)
    registries = pl.registries
    assert registries.navigation.unregister("plugin:nobody") == 0
    assert registries.widgets.get("plugin:hello.counter") is not None
    assert registries.search.provider("plugin:hello.greetings") is not None
    assert registries.permissions.get("plugin:hello.view") is not None
    assert registries.event_types.get("plugin.hello.greeted") is not None
    assert registries.event_types.get("plugin.hello.waved").automatable
    assert registries.capabilities.system_providers("plugin.hello.greeter")
    assert pl.catalogs.unregister("plugin:nobody") == 0 and pl.themes.themes["hello-dusk"]["enabled"]
    widget = registries.widgets.get("plugin:hello.counter")
    assert widget is not None and widget.definition.required_permission == "plugin:hello.view"
    await check_guard(pl.module, "hello", "boom")
    await pl.module.lifecycle.disable(SYSTEM, "hello")
    await check_removal(pl.module, "hello")


class Noop:
    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        return ActivationResult("active")

    async def deactivate(self, ownership: OwnershipView) -> None:
        return None


async def test_conflicts_are_deterministic_and_flagged(pl: PlHarness) -> None:
    code = """
    from portalab.sdk import PluginContext


    def register(ctx: PluginContext) -> None:
        ctx.provide("identity.members", object())
    """
    await pl.installed(pl.package("first", code=code))
    await pl.installed(pl.package("second", code=code))
    diagnostics = {key: await pl.module.ledger.entries(key) for key in ("first", "second")}
    states = {
        key: [(e.point, e.state) for e in entries if e.state != "removed"]
        for key, entries in diagnostics.items()
    }
    # identity.members accepts a single provider: identity owns it; both plugins are flagged, nothing breaks
    assert states["first"] == [("capability", "conflict")] and states["second"] == [
        ("capability", "conflict")
    ]
    pl.registries.product_types.register(ProductType("plugin:second.thing", "plugin:second", Noop()))
    with pytest.raises(ValueError, match="already registered"):
        pl.registries.product_types.register(ProductType("plugin:second.thing", "plugin:first", Noop()))
