"""007 T018 — upcasters: stored events keep their version; consumers declaring a newer version receive an
upcast copy; a missing step is an error, never a silent change."""

import pytest

from portalab.modules.events.registry.upcasters import UpcasterRegistry

pytestmark = pytest.mark.unit


def test_upcast_chain_and_owner() -> None:
    registry = UpcasterRegistry()
    registry.register("media.played", 1, lambda p: {"seconds": p["minutes"] * 60}, owner="module:media")
    registry.register("media.played", 2, lambda p: {**p, "unit": "s"}, owner="module:media")
    original = {"minutes": 2}
    assert registry.upcast("media.played", original, 1, 3) == {"seconds": 120, "unit": "s"}
    assert original == {"minutes": 2}  # the stored payload is untouched
    assert registry.upcast("media.played", {"x": 1}, 3, 3) == {"x": 1}
    with pytest.raises(LookupError):
        registry.upcast("media.played", {}, 0, 2)
    assert registry.unregister("module:media") == 2
