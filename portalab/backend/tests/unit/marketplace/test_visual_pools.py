"""Issue 153: a booster may draw from chosen visual packs (``visual:<pack>``) — what each live pack sells, as
the visuals module keeps it — alongside the shop's own packs (bundles)."""

from types import SimpleNamespace

from portalab.capabilities.visuals import PackProducts, pack_products
from portalab.modules.marketplace.openings.service import pool_keys


def _row(key: str, kind: str = "badge", products: list[str] | None = None) -> tuple[object, object]:
    return SimpleNamespace(key=key, type=kind), SimpleNamespace(payload={"products": products or []})


def test_a_pool_of_visual_packs() -> None:
    rows = [_row("pack_cosmos", "bundle", ["frame_a"]), _row("frame_a"), _row("abyss_a"), _row("abyss_b")]
    pack_products.replace({"abysses": ["abyss_a", "abyss_b"], "nordlys": ["aurora_a"]})
    try:
        assert pool_keys(rows, ("visual:abysses",)) == {"abyss_a", "abyss_b"}  # type: ignore[arg-type]
        both = pool_keys(rows, ("visual:nordlys", "pack_cosmos"))  # type: ignore[arg-type]
        assert both == {"aurora_a", "frame_a"}
        assert pool_keys(rows, ("visual:gone",)) == set()  # type: ignore[arg-type]  # nothing: an empty pool
        assert pool_keys(rows, ()) is None  # type: ignore[arg-type]
    finally:
        pack_products.replace({})


async def test_pack_products_ask_for_a_fresh_list() -> None:
    held = PackProducts()
    calls: list[int] = []

    async def load() -> None:
        calls.append(1)
        held.replace({"abysses": ["abyss_a"], "empty": []})

    held.loader = load
    await held.ready()
    assert calls == [1] and held.of("abysses") == {"abyss_a"} and held.packs() == {"abysses": 1}
