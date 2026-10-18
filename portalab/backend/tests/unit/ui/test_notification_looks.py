"""027 — notification looks: the free styles and animations are always allowed; the ones sold in the shop
only to their owners — enforced when the preference is saved."""

from uuid import UUID

from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.themes import COSMETICS, COSMETICS_SPEC
from portalab.modules.ui.looks import NotificationLooks

OWNER = UUID(int=1)


class _Shop:
    async def sold(self, kind: str, field: str) -> frozenset[str]:
        return frozenset({"neon", "glass"} if kind == "notification_style" else {"bounce", "slide"})

    async def owned(self, user_id: UUID, kind: str, field: str) -> frozenset[str]:
        return frozenset({"neon"}) if user_id == OWNER and kind == "notification_style" else frozenset()

    async def equipped(self, user_id: UUID) -> dict[str, object]:
        return {}


async def test_sold_looks_need_ownership() -> None:
    registry = CapabilityRegistry()
    registry.declare(COSMETICS_SPEC)
    registry.provide(COSMETICS, _Shop(), instance_ref="shop", owner="test")
    looks = NotificationLooks(registry)
    style = looks.validator("ui.notificationStyle")
    assert await style("neon", str(OWNER)) == []  # owned
    assert await style("glass", str(OWNER)) != []  # sold, not owned
    assert await style("pill", None) == []  # free
    animation = looks.validator("ui.notificationAnimation")
    assert await animation("slide", None) == []  # a free animation stays free even if someone sells it
    assert await animation("bounce", str(OWNER)) != []
    catalog = await looks.catalog(OWNER)
    assert {s["key"]: s["locked"] for s in catalog["styles"]}["glass"] is True
    assert {s["key"]: s["locked"] for s in catalog["styles"]}["neon"] is False


async def test_without_a_shop_everything_is_allowed() -> None:
    looks = NotificationLooks(CapabilityRegistry())
    assert await looks.validator("ui.notificationStyle")("neon", None) == []


async def test_ambient_and_celebration_follow_ownership() -> None:
    """027: the ambient layer and the celebration are cosmetics too — ``theme`` and ``none`` stay free."""

    class _Ambients(_Shop):
        async def sold(self, kind: str, field: str) -> frozenset[str]:
            return frozenset({"snow"} if kind == "ambient" else {"coins"} if kind == "effect" else set())

        async def owned(self, user_id: UUID, kind: str, field: str) -> frozenset[str]:
            return frozenset({"snow"}) if user_id == OWNER and kind == "ambient" else frozenset()

    registry = CapabilityRegistry()
    registry.declare(COSMETICS_SPEC)
    registry.provide(COSMETICS, _Ambients(), instance_ref="shop", owner="test")
    looks = NotificationLooks(registry)
    ambient = looks.validator("ui.ambient")
    assert await ambient("snow", str(OWNER)) == []
    assert await ambient("snow", None) != []
    assert await ambient("theme", None) == [] and await ambient("none", None) == []
    celebration = looks.validator("ui.celebration")
    assert await celebration("coins", str(OWNER)) != []
    assert await celebration("sparkle", None) == []
    assert set(NotificationLooks.SETTINGS) >= {"ui.ambient", "ui.celebration", "ui.palette"}


async def test_level_up_looks_follow_ownership() -> None:
    """027: how a level-up is shown — ``classic`` is free, the others are worn by their owners only."""

    class _LevelUps(_Shop):
        async def sold(self, kind: str, field: str) -> frozenset[str]:
            return frozenset({"cosmic", "arcade"}) if kind == "level_up" else frozenset()

        async def owned(self, user_id: UUID, kind: str, field: str) -> frozenset[str]:
            return frozenset({"arcade"}) if user_id == OWNER and kind == "level_up" else frozenset()

    registry = CapabilityRegistry()
    registry.declare(COSMETICS_SPEC)
    registry.provide(COSMETICS, _LevelUps(), instance_ref="shop", owner="test")
    looks = NotificationLooks(registry)
    level_up = looks.validator("ui.levelUp")
    assert await level_up("classic", None) == []
    assert await level_up("arcade", str(OWNER)) == []
    assert await level_up("cosmic", str(OWNER)) != []
    catalog = await looks.catalog(OWNER)
    shown = {b["key"]: b["locked"] for b in catalog["level_ups"]}
    assert shown["cosmic"] is True and shown["arcade"] is False and shown["classic"] is False


async def test_ambiences_carry_their_rarity() -> None:
    """#71, #72: the looks come with the product selling them (rarity, price), shown in Appearance; free ones
    have none, and a shop without that detail changes nothing."""

    class _Rarities(_Shop):
        async def sold(self, kind: str, field: str) -> frozenset[str]:
            return frozenset({"lavalamp"}) if kind == "ambient" else frozenset()

        async def details(self, kind: str, field: str) -> dict[str, dict[str, object]]:
            if (kind, field) == ("notification_style", "style"):
                return {"neon": {"product": "notif_neon", "rarity": "rare", "price": 400}}
            if (kind, field) != ("ambient", "ambient"):
                return {}
            return {"lavalamp": {"product": "ambient_lavalamp", "rarity": "legendary", "price": 1500}}

    registry = CapabilityRegistry()
    registry.declare(COSMETICS_SPEC)
    registry.provide(COSMETICS, _Rarities(), instance_ref="shop", owner="test")
    catalog = await NotificationLooks(registry).catalog(OWNER)
    ambients = {a["key"]: a for a in catalog["ambients"]}
    assert {s["key"]: s for s in catalog["styles"]}["neon"]["rarity"] == "rare"  # #72: every kind of look
    assert ambients["lavalamp"]["rarity"] == "legendary" and ambients["lavalamp"]["locked"] is True
    assert ambients["lavalamp"]["price"] == 1500
    assert "rarity" not in ambients["snow"]

    plain = CapabilityRegistry()
    plain.declare(COSMETICS_SPEC)
    plain.provide(COSMETICS, _Shop(), instance_ref="shop", owner="test")
    assert "rarity" not in (await NotificationLooks(plain).catalog(OWNER))["ambients"][0]


async def test_a_style_whose_pack_is_off_shows_to_its_owner_only() -> None:
    """028 (T081): a style of a visual pack switched off — listed for its owner, « currently unavailable »;
    hidden from the others (nobody may pick it until the pack comes back)."""
    from portalab.capabilities.visuals import live_looks

    class _Held(_Shop):
        async def waiting(self, user_id: UUID, kind: str, field: str) -> dict[str, dict[str, int]]:
            owner = user_id == OWNER and kind == "notification_style"
            return {"tide": {"unavailable": 1}} if owner else {}

    registry = CapabilityRegistry()
    registry.declare(COSMETICS_SPEC)
    registry.provide(COSMETICS, _Held(), instance_ref="shop", owner="test")
    looks = NotificationLooks(registry)
    live_looks.replace({}, held={"notification_style": ["tide"]})
    try:
        mine = {s["key"]: s for s in (await looks.catalog(OWNER))["styles"]}
        assert mine["tide"]["waiting"] == {"unavailable": 1}
        assert "tide" not in {s["key"] for s in (await looks.catalog(UUID(int=2)))["styles"]}
        assert await looks.validator("ui.notificationStyle")("tide", str(OWNER)) != []
        assert live_looks.listed("notification_style")[-1] == "tide"
    finally:
        live_looks.replace({})


async def test_looks_of_plugins_kinds_of_visuals() -> None:
    """030: a kind of visual an enabled plugin adds (message bubbles) is listed in Appearance with the looks
    the shop sells of it, the member's own to choose; the preference keeps those kinds and owned looks."""
    from portalab.capabilities.visuals import PluginVisualType, plugin_visual_types

    kind = "plugin:messenger.bubble"

    class _Bubbles(_Shop):
        async def sold(self, kind_: str, field: str) -> frozenset[str]:
            return frozenset({"aurora", "ember"}) if (kind_, field) == (kind, "look") else frozenset()

        async def owned(self, user_id: UUID, kind_: str, field: str) -> frozenset[str]:
            return frozenset({"aurora"}) if user_id == OWNER and kind_ == kind else frozenset()

        async def details(self, kind_: str, field: str) -> dict[str, dict[str, object]]:
            names = {"en": "Aurora bubbles"}
            return {"aurora": {"product": "messenger_bubble_aurora", "rarity": "rare", "names": names}}

    registry = CapabilityRegistry()
    registry.declare(COSMETICS_SPEC)
    registry.provide(COSMETICS, _Bubbles(), instance_ref="shop", owner="test")
    looks = NotificationLooks(registry)
    plugin_visual_types.register(
        PluginVisualType(kind, "plugin:messenger", "plugin.messenger:type.bubble", ("css",), "message-circle")
    )
    try:
        (listed,) = [k for k in await looks.plugin_catalog(OWNER) if k["type"] == kind]
        assert listed["plugin"] == "messenger" and listed["icon"] == "message-circle"
        shown = {look["key"]: look for look in listed["looks"]}
        assert shown["aurora"]["locked"] is False and shown["aurora"]["names"]["en"] == "Aurora bubbles"
        assert shown["ember"]["locked"] is True
        assert await looks.plugin_errors({kind: "aurora"}, str(OWNER)) == []
        assert await looks.plugin_errors({kind: "ember"}, str(OWNER)) != []  # sold, not owned
        assert await looks.plugin_errors({"plugin:gone.kind": "aurora"}, str(OWNER)) != []
        assert await looks.plugin_errors({kind: None}, str(OWNER)) == []
        assert await looks.plugin_errors({}) == []
    finally:
        plugin_visual_types.remove("plugin:messenger")
