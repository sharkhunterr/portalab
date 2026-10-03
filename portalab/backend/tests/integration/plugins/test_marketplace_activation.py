"""023 T027 — Admin-installed and Marketplace-linked plugins share one lifecycle; ``ExtensionActivation``
grants ``plugin:<key>.use`` (per-user plugins) and reports ``active|needs_configuration|failed|
incompatible``; deactivation removes the grant; the Marketplace ``plugin`` product handler uses it."""

import pytest

from portalab.capabilities.marketplace import OwnershipView
from portalab.capabilities.plugins import EXTENSION_ACTIVATION
from portalab.modules.marketplace.types.registry import ExtensionHandler
from tests.integration.plugins.conftest import SYSTEM, PlHarness

pytestmark = pytest.mark.integration


async def test_per_user_activation(pl: PlHarness) -> None:
    await pl.installed(pl.package("vip", manifest={"scope": "user"}))
    [registration] = pl.module.capabilities.system_providers(EXTENSION_ACTIVATION)
    activation = registration.provider
    engine = pl.ev.full.authz.engine
    ursula = pl.people["ursula"]
    assert not await engine.is_allowed(pl.p("ursula"), "plugin:vip.use")
    assert await activation.activate_for_user("vip", ursula) == "active"
    assert await engine.is_allowed(pl.p("ursula"), "plugin:vip.use")
    assert not await engine.is_allowed(pl.p("ulrich"), "plugin:vip.use")
    await activation.deactivate_for_user("vip", ursula)
    assert not await engine.is_allowed(pl.p("ursula"), "plugin:vip.use")
    assert await activation.status("ghost", ursula) == "incompatible"

    handler = ExtensionHandler(pl.module.capabilities)
    view = OwnershipView(ursula, ursula, "vip_pass", "plugin", {"extension": "vip"})
    assert (await handler.activate(view)).state == "active"
    assert await engine.is_allowed(pl.p("ursula"), "plugin:vip.use")
    await handler.deactivate(view)
    await pl.module.lifecycle.disable(SYSTEM, "vip")
    assert await activation.activate_for_user("vip", ursula) == "failed"  # not enabled
    assert (await handler.activate(view)).state == "failed"
