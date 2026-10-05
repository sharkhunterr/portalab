"""027 — packs and notification looks: buying a pack grants every product it lists (one already owned is
kept, an unknown one skipped); notification styles and animations sold as products are read through
``marketplace.cosmetics`` — sold to everyone, owned by the buyers (directly or through a pack)."""

import pytest

from portalab.capabilities.themes import COSMETICS
from tests.integration.marketplace.conftest import MkHarness, published

pytestmark = pytest.mark.integration


async def test_pack_grants_its_products_and_looks_follow_ownership(mk: MkHarness) -> None:
    await published(mk, "notif_neon", "notification_style", payload={"style": "neon"})
    await published(mk, "notif_bounce", "notification_animation", payload={"animation": "bounce"})
    await published(mk, "badge_owl", "badge")
    await published(
        mk, "pack_night", "bundle", payload={"products": ["notif_neon", "badge_owl", "does_not_exist"]}
    )
    zoe, max_ = mk.p("ursula"), mk.p("ulrich")
    await mk.module.purchases.acquire(zoe, "badge_owl", "k1")  # already owned before the pack

    pack = await mk.module.purchases.acquire(zoe, "pack_night", "k2")
    assert pack.state == "active"
    owned = set(await mk.module.entitlements.owned_by_type(zoe.user_id, "notification_style"))  # type: ignore[arg-type]
    assert owned == {"notif_neon"}
    assert set(await mk.module.entitlements.owned_by_type(zoe.user_id, "badge")) == {"badge_owl"}  # type: ignore[arg-type]

    cosmetics = mk.module.capabilities.system_providers(COSMETICS)[0].provider
    assert await cosmetics.sold("notification_style", "style") == {"neon"}
    assert await cosmetics.sold("notification_animation", "animation") == {"bounce"}
    assert await cosmetics.owned(zoe.user_id, "notification_style", "style") == {"neon"}
    assert await cosmetics.owned(max_.user_id, "notification_style", "style") == frozenset()

    await published(mk, "pack_empty", "bundle", payload={"products": []})
    empty = await mk.module.purchases.acquire(max_, "pack_empty", "k3")
    assert empty.state != "active"  # an empty pack grants nothing and is not activated
