"""027 — the shop previews a product before it is bought: only the whitelisted payload fields of its type
(the style, the banner, a pack's products…), never an extension's or an access product's details."""

from portalab.modules.marketplace.api.catalog import product_out
from portalab.modules.marketplace.models import Product, ProductVersion


def _out(type_: str, payload: dict[str, object]) -> dict[str, object]:
    product = Product(key="p", type=type_, state="published", current_version=1, repeatable=False)
    product.rarity, product.featured, product.poster_effect = "rare", False, "auto"
    version = ProductVersion(
        version=1, price_coins=10, conditions=[], refund_policy={}, names={"en": "P"}, payload=payload
    )
    version.descriptions, version.config_required = {}, False
    return product_out(product, version, owned=False).preview


def test_preview_shows_only_whitelisted_fields() -> None:
    assert _out("notification_style", {"style": "neon", "secret": "x"}) == {"style": "neon"}
    assert _out("bundle", {"products": ["a", "b"]}) == {"products": ["a", "b"]}
    assert _out("profile_banner", {"banner": "synthwave"}) == {"banner": "synthwave"}
    assert _out("access", {"permission": "admin.all"}) == {}
    assert _out("plugin", {"extension": "x", "config_required": True}) == {}
