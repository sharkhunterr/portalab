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
