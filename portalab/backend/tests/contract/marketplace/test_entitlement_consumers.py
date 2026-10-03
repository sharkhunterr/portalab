"""015 T033 — ``marketplace.entitlements`` honours the contract its consumers rely on: 009 widget products,
022 themes and 017 ``product_owned`` call ``owns(user, product_key)``; Community shows owned badges and
titles in the ``cosmetics`` profile section; refunded or revoked products stop counting."""

import pytest

from portalab.capabilities.dashboard import ENTITLEMENTS, EntitlementReader
from tests.integration.marketplace.conftest import MkHarness, published

pytestmark = pytest.mark.integration


async def test_consumers_contract(mk: MkHarness) -> None:
    [registration] = mk.module.capabilities.system_providers(ENTITLEMENTS)
    reader = registration.provider
    assert isinstance(reader, EntitlementReader)
    await published(mk, "owl", "badge", price_coins=10, payload={"label": "Owl"})
    await published(mk, "boss_title", "title", payload={"label": "Boss"})
    await mk.coins("ursula", 50)
    owl = await mk.module.purchases.acquire(mk.p("ursula"), "owl", "1")
    await mk.module.purchases.acquire(mk.p("ursula"), "boss_title", "2")
    user = mk.people["ursula"]
    assert await reader.owns(user, "owl") and not await reader.owns(mk.people["ulrich"], "owl")
    assert await mk.module.entitlements.owned_by_type(user, "badge") == ["owl"]

    section = mk.module.sections.get("cosmetics")
    assert section is not None and section.datum_class == "progression"
    shown = await section.provider(user, mk.p("ulrich"))
    assert shown.state == "available" and shown.data == {"badges": ["owl"], "titles": ["boss_title"]}

    await mk.module.refunds.refund(mk.p("ursula"), owl.id, "Changed my mind")
    assert not await reader.owns(user, "owl")
    assert (await section.provider(user, mk.p("ulrich"))).data["badges"] == []
