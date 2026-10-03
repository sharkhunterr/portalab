"""015 T025 — activation handlers: immediate activation on acquisition; ``needs_configuration`` until the
owner configures; an incompatible or failing activation is isolated (ownership kept, retried, other
products unaffected); ``access`` grants only Admin-allowed, non-reserved permissions and removes them on
revoke; widget/theme/statistic ownership is read through ``marketplace.entitlements``."""

from dataclasses import replace
from datetime import timedelta

import pytest
from httpx import AsyncClient

from portalab.capabilities.dashboard import ENTITLEMENTS, WidgetDefinition, WidgetPayload
from portalab.capabilities.marketplace import ActivationResult, OwnershipView, ProductType
from tests.integration.identity.helpers import login
from tests.integration.marketplace.conftest import MkHarness, published

pytestmark = pytest.mark.integration


class Flaky:
    def __init__(self) -> None:
        self.fail = True

    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        if self.fail:
            raise RuntimeError("extension service down")
        return ActivationResult("active")

    async def deactivate(self, ownership: OwnershipView) -> None:
        return None


class Data:
    async def load(self, principal: object, config: object, ctx: object) -> WidgetPayload:
        raise NotImplementedError


async def test_activation_paths(mk: MkHarness, client: AsyncClient) -> None:
    mk.module.widgets.register(
        WidgetDefinition(
            key="test.widget", owner="module:test", title_key="t", required_permission="users.self.manage"
        ),
        Data(),  # type: ignore[arg-type]
    )
    await published(mk, "chart", "widget", payload={"widget": "test.widget"})
    await published(mk, "ghost", "widget", payload={"widget": "test.missing"})
    await published(mk, "tool", "feature", payload={"extension": "tool"}, config_required=True)
    flaky = Flaky()
    mk.module.product_types.register(ProductType("fragile", "module:test", flaky))
    await published(mk, "fragile_thing", "fragile")
    user = mk.p("ursula")

    chart = await mk.module.purchases.acquire(user, "chart", "1")
    ghost = await mk.module.purchases.acquire(user, "ghost", "2")
    tool = await mk.module.purchases.acquire(user, "tool", "3")
    fragile = await mk.module.purchases.acquire(user, "fragile_thing", "4")
    assert (chart.state, ghost.state, tool.state, fragile.state) == (
        "active",
        "activation_failed",
        "needs_configuration",
        "activation_failed",
    )
    [entitlements] = mk.module.capabilities.system_providers(ENTITLEMENTS)
    assert await entitlements.provider.owns(mk.people["ursula"], "chart")
    assert await entitlements.provider.owns(mk.people["ursula"], "fragile_thing")  # ownership kept
    assert not await entitlements.provider.owns(mk.people["ulrich"], "chart")

    await login(client, "ursula")
    configured = await client.post(
        f"/api/v1/me/marketplace/owned/{tool.id}/configure", json={"configuration": {"mode": "on"}}
    )
    assert configured.json()["state"] == "active"
    flaky.fail = False
    mk.clock.advance(timedelta(minutes=mk.module.config.activation_retry_minutes))
    assert await mk.module.activation.retry() == 2  # ghost stays incompatible, fragile recovers
    states = {o["product_key"]: o["state"] for o in (await client.get("/api/v1/me/marketplace/owned")).json()}
    assert states == {
        "chart": "active",
        "ghost": "activation_failed",
        "tool": "active",
        "fragile_thing": "active",
    }
    assert len(await mk.events("marketplace.unlock")) == 3


async def test_access_products(mk: MkHarness, monkeypatch: pytest.MonkeyPatch) -> None:
    from portalab.capabilities.user_grants import CAPABILITY as USER_GRANTS
    from portalab.core.permissions import default_permissions

    granted: list[tuple[str, str]] = []

    async def grant(user_id: object, permission_key: str, **kwargs: object) -> None:
        granted.append(("grant", permission_key))

    async def revoke(user_id: object, permission_key: str, **kwargs: object) -> bool:
        granted.append(("revoke", permission_key))
        return True

    [real] = mk.module.capabilities.system_providers(USER_GRANTS)  # the 003 provider, observed
    monkeypatch.setattr(real.provider, "grant", grant)
    monkeypatch.setattr(real.provider, "revoke", revoke)
    reserved = next(d.key for d in default_permissions.all() if d.reserved)
    mk.module.config = replace(mk.module.config, access_allowed_permissions=["statistics.read", reserved])
    await published(mk, "stats_access", "access", payload={"permission": "statistics.read"})
    await published(mk, "admin_access", "access", payload={"permission": reserved})
    await published(mk, "other_access", "access", payload={"permission": "news.publish"})
    ok = await mk.module.purchases.acquire(mk.p("ursula"), "stats_access", "1")
    reserved_try = await mk.module.purchases.acquire(mk.p("ursula"), "admin_access", "2")
    not_allowed = await mk.module.purchases.acquire(mk.p("ursula"), "other_access", "3")
    assert (ok.state, reserved_try.state, not_allowed.state) == (
        "active",
        "activation_failed",
        "activation_failed",
    )
    await mk.module.revocations.revoke(mk.p("boss"), ok.id, "withdrawn_for_cause", "Policy change")
    assert granted == [("grant", "statistics.read"), ("revoke", "statistics.read")]
