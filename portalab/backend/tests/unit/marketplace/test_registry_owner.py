"""015 T036 — the product-type registry is owner-tagged: ``unregister(owner)`` removes every type of that
owner; plugin types are namespaced; a key cannot be taken over by another owner."""

import pytest

from portalab.capabilities.marketplace import (
    ActivationResult,
    OwnershipView,
    ProductType,
    ProductTypeRegistry,
)


class Noop:
    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        return ActivationResult("active")

    async def deactivate(self, ownership: OwnershipView) -> None:
        return None


def test_owner_tagged_registry() -> None:
    registry = ProductTypeRegistry()
    registry.register(ProductType("badge", "module:marketplace", Noop()))
    registry.register(ProductType("plugin:acme.sticker", "plugin:acme", Noop()))
    registry.register(ProductType("plugin:acme.frame", "plugin:acme", Noop()))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(ProductType("badge", "plugin:acme", Noop()))
    with pytest.raises(ValueError, match="namespaced"):
        registry.register(ProductType("sticker", "plugin:acme", Noop()))
    assert registry.unregister("plugin:acme") == 2
    assert [t.key for t in registry.all()] == ["badge"]
