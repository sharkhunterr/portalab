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


async def test_profile_looks_follow_ownership(mk: MkHarness) -> None:
    from portalab.core.errors import ValidationFailed
    from portalab.modules.marketplace.looks.service import LookLocked

    await published(mk, "banner_synth", "profile_banner", payload={"banner": "synthwave"})
    await published(mk, "frame_gold", "avatar_frame", payload={"frame": "gold"})
    await published(mk, "backdrop_feature", "profile_backdrop", payload={"feature": "backdrop"})
    ursula = mk.p("ursula")
    user = ursula.user_id
    assert user is not None
    looks = mk.module.looks
    assert (await looks.equip(user, "banner", "aurora"))["banner"] == "aurora"  # not sold: free
    with pytest.raises(LookLocked):
        await looks.equip(user, "banner", "synthwave")
    with pytest.raises(LookLocked):
        await looks.equip(user, "backdrop", {"object_id": str(user), "ref": "/backdrop.jpg"})
    await mk.module.purchases.acquire(ursula, "banner_synth", "b1")
    await mk.module.purchases.acquire(ursula, "backdrop_feature", "b2")
    assert (await looks.equip(user, "banner", "synthwave"))["banner"] == "synthwave"
    worn = await looks.equip(user, "backdrop", {"object_id": str(user), "ref": "/abc.jpg", "title": "Dune"})
    assert worn["backdrop"]["ref"] == "/abc.jpg" and worn["backdrop"]["title"] == "Dune"
    with pytest.raises(ValidationFailed):
        await looks.equip(user, "backdrop", {"object_id": str(user), "ref": "https://evil.example/x.jpg"})
    catalog = await looks.catalog(user)
    frames = {f["key"]: f["locked"] for f in catalog["frames"]}
    assert frames["gold"] is True and frames["simple"] is False and catalog["backdrop"]["unlocked"]
    assert (await looks.equip(user, "banner", None)).get("banner") is None  # taken off


async def test_profile_background_name_title_and_badges(mk: MkHarness) -> None:
    """027: an animated background and a name style follow ownership like banners; a member shows one of
    their titles and up to three of their badges (with their animated style), never someone else's."""
    from portalab.modules.marketplace.looks.service import LookLocked

    await published(mk, "bg_snow", "profile_background", payload={"background": "snow"})
    await published(mk, "name_fire", "name_style", payload={"style": "fire"})
    await published(mk, "title_legend", "title", payload={"label": "Legend", "style": "gold"})
    for key, label in (("b1", "One"), ("b2", "Two"), ("b3", "Three"), ("b4", "Four")):
        await published(mk, key, "badge", payload={"label": label, "icon": "star", "style": "pulse"})
    ursula = mk.p("ursula")
    user = ursula.user_id
    assert user is not None
    looks = mk.module.looks
    with pytest.raises(LookLocked):
        await looks.equip(user, "background", "snow")
    with pytest.raises(LookLocked):
        await looks.equip(user, "title", "title_legend")
    for key in ("bg_snow", "name_fire", "title_legend", "b1", "b2", "b3", "b4"):
        await mk.module.purchases.acquire(ursula, key, f"k-{key}")
    assert (await looks.equip(user, "background", "snow"))["background"] == "snow"
    assert (await looks.equip(user, "name", "fire"))["name"] == "fire"
    worn = await looks.equip(user, "title", "title_legend")
    assert worn["title"] == {"key": "title_legend", "label": "Legend", "icon": None, "style": "gold"}
    shown = await looks.equip(user, "badges", ["b1", "b2", "b3", "b4"])
    assert [badge["label"] for badge in shown["badges"]["items"]] == ["One", "Two", "Three"]  # three at most
    assert shown["badges"]["items"][0]["style"] == "pulse"
    with pytest.raises(LookLocked):
        await looks.equip(mk.people["ulrich"], "badges", ["b1"])  # not theirs
    catalog = await looks.catalog(user)
    assert {t["key"] for t in catalog["titles"]} == {"title_legend"}
    assert len(catalog["badges"]) == 4
    assert {b["key"]: b["locked"] for b in catalog["backgrounds"]}["snow"] is False
    assert (await looks.equip(user, "badges", None)).get("badges") is None
