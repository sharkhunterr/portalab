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
    assert {k: v for k, v in worn["title"].items() if k != "rarity"} == {
        "key": "title_legend",
        "label": "Legend",
        "icon": None,
        "style": "gold",
    }
    assert "rarity" in worn["title"]  # #79: shown with it
    shown = await looks.equip(user, "badges", ["b1", "b2", "b3", "b4"])
    assert [badge["label"] for badge in shown["badges"]["items"]] == ["One", "Two", "Three"]  # three at most
    assert shown["badges"]["items"][0]["style"] == "pulse"
    with pytest.raises(LookLocked):
        await looks.equip(mk.people["ulrich"], "badges", ["b1"])  # not theirs
    catalog = await looks.catalog(user)
    assert {t["key"] for t in catalog["titles"]} == {"title_legend"}
    assert len(catalog["badges"]) == 4
    assert catalog["in_shop"]["title"] == 0 and catalog["in_shop"]["badge"] >= 0  # #79: the rest, counted
    assert (await looks.catalog(mk.people["ulrich"]))["in_shop"]["title"] >= 1
    assert {b["key"]: b["locked"] for b in catalog["backgrounds"]}["snow"] is False
    assert (await looks.equip(user, "badges", None)).get("badges") is None


async def test_project_launch_opens_a_community_proposal(mk: MkHarness) -> None:
    """027: buying a project launch asks for a title and a pitch, then opens the project as a proposal."""
    from sqlalchemy import select

    from portalab.modules.marketplace.models import Project

    await published(mk, "launch", "project_launch", payload={"kind": "feature"})
    ursula = mk.p("ursula")
    ownership = await mk.module.purchases.acquire(ursula, "launch", "l1")
    assert ownership.state == "needs_configuration"
    done = await mk.module.activation.configure(
        ursula, ownership.id, {"title": "Dark mode for the wiki", "pitch": "Reading at night."}
    )
    assert done.state == "active"
    async with mk.database.session() as session:
        project = await session.scalar(
            select(Project).where(Project.proposal_ref == f"purchase:{ownership.id}")
        )
    assert project is not None
    assert (project.title, project.state, project.proposer_id) == (
        "Dark mode for the wiki",
        "proposal",
        mk.people["ursula"],
    )
    again = await mk.module.activation.activate(ownership.id)  # re-activation never opens a second project
    assert again.state == "active"


async def test_shop_window_widget_leaves_out_what_the_viewer_owns(mk: MkHarness) -> None:
    """027: the dashboard's shop window shows what is for sale — never what the viewer already owns, nor a
    project launch — with its rarity and price, and how many products the shop holds."""
    from portalab.capabilities.i18n import LocaleContext
    from portalab.modules.marketplace.integrations import FeaturedWidget

    for key in ("badge_a", "badge_b"):
        await published(mk, key, "badge")
    await published(mk, "launch", "project_launch", payload={"kind": "feature"})
    ursula = mk.p("ursula")
    await mk.module.purchases.acquire(ursula, "badge_a", "w1")
    loaded = await FeaturedWidget(mk.module.catalog).load(ursula, {}, LocaleContext())
    assert loaded.data is not None
    assert [i["key"] for i in loaded.data["items"]] == ["badge_b"] and loaded.data["total"] == 1
    assert {"rarity", "price", "type", "featured"} <= set(loaded.data["items"][0])


async def test_level_badge_slot_and_reward_only_designs(mk: MkHarness) -> None:
    """027: the level badge's look is a profile slot — ``classic`` free, a sold look only for its owners —
    and a design given by an achievement (an « unavailable » product, out of sale) stays exclusive."""
    import pytest

    from portalab.modules.marketplace.looks.service import LookLocked

    await published(mk, "level_neon", "level_badge", payload={"style": "neon"})
    await published(mk, "level_crown", "level_badge", payload={"style": "crown"})
    await mk.module.catalog.move(mk.p("boss"), "level_crown", "unavailable")  # an achievement's reward
    looks = mk.module.looks
    user = mk.people["ursula"]
    assert (await looks.equip(user, "level", "classic"))["level"] == "classic"
    with pytest.raises(LookLocked):
        await looks.equip(user, "level", "neon")
    with pytest.raises(LookLocked):
        await looks.equip(user, "level", "crown")  # out of sale, yet not free for everyone
    await mk.module.grants.grant(mk.p("boss"), user, "level_crown", "achievement")
    assert (await looks.equip(user, "level", "crown"))["level"] == "crown"
    catalog = await looks.catalog(user)
    shown = {c["key"]: c["locked"] for c in catalog["levels"]}
    assert shown["crown"] is False and shown["neon"] is True and shown["classic"] is False


async def test_an_ambience_sold_only_as_ambience_is_no_free_profile_background(mk: MkHarness) -> None:
    """#79: a premium ambience is worn behind a profile by its owners only — owning the ambience unlocks it
    (before, an ambience sold only as an ambience was free as a profile background)."""
    from portalab.modules.marketplace.looks.service import LookLocked

    await published(mk, "ambient_lavalamp", "ambient", payload={"ambient": "lavalamp"})
    looks = mk.module.looks
    ursula = mk.p("ursula")
    user = ursula.user_id
    assert user is not None
    with pytest.raises(LookLocked):
        await looks.equip(user, "background", "lavalamp")
    await mk.module.purchases.acquire(ursula, "ambient_lavalamp", "k-lava")
    assert (await looks.equip(user, "background", "lavalamp"))["background"] == "lavalamp"
