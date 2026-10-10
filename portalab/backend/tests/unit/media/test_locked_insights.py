"""027 — Media statistics sold in the shop (``statistic`` products ``media.insights.<name>``): locked for
members who do not own them, open for owners; nothing locked when the shop sells none, nor for media
managers (061)."""

from types import SimpleNamespace
from uuid import UUID

from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.themes import COSMETICS, COSMETICS_SPEC
from portalab.core.authz_port import Principal
from portalab.modules.media.api.router import _locked_insights

OWNER = UUID(int=7)


class _Shop:
    def __init__(self, sold: set[str]) -> None:
        self._sold = frozenset(sold)

    async def sold(self, kind: str, field: str) -> frozenset[str]:
        return self._sold if kind == "statistic" else frozenset()

    async def owned(self, user_id: UUID, kind: str, field: str) -> frozenset[str]:
        return frozenset({"media.insights.genres"}) if user_id == OWNER else frozenset()

    async def equipped(self, user_id: UUID) -> dict[str, object]:
        return {}


class _Authorizer:
    def __init__(self, manager: bool) -> None:
        self.manager = manager

    async def is_allowed(self, principal: Principal, permission: str) -> bool:
        return self.manager


def _module(sold: set[str], manager: bool = False) -> SimpleNamespace:
    registry = CapabilityRegistry()
    registry.declare(COSMETICS_SPEC)
    registry.provide(COSMETICS, _Shop(sold), instance_ref="shop", owner="test")
    return SimpleNamespace(capabilities=registry, authorizer=_Authorizer(manager))


async def test_sold_statistics_are_locked_until_owned() -> None:
    module = _module({"media.insights.genres", "media.insights.box_office", "other.thing"})
    assert await _locked_insights(module, Principal(user_id=UUID(int=1))) == ["box_office", "genres"]
    assert await _locked_insights(module, Principal(user_id=OWNER)) == ["box_office"]
    assert await _locked_insights(_module(set()), Principal(user_id=OWNER)) == []
    manager = _module({"media.insights.genres"}, manager=True)
    assert await _locked_insights(manager, Principal(user_id=UUID(int=1))) == []
