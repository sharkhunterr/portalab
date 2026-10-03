"""Baseline product types (T020, T026; R7, R10): ``widget``, ``theme``, ``statistic`` (read by 009, 022 and
017 through ``marketplace.entitlements``), cosmetic ``badge``/``title``/``effect`` (shown in profiles),
``feature``/``plugin`` (portal-level code is installed by the Admin when publishing — ownership is per
user; 023 activation is a stub until step 27), ``access`` (a scoped grant limited to the Admin allow-list,
never an Admin-reserved permission, removed on revoke) and ``quota`` (units credited by Media's
``RequestQuotaService``; Marketplace never measures nor consumes quota, never sells priority)."""

from collections.abc import Callable
from typing import Any

from portalab.capabilities.dashboard import WidgetRegistry
from portalab.capabilities.marketplace import (
    ActivationResult,
    OwnershipView,
    ProductType,
    ProductTypeRegistry,
)
from portalab.capabilities.media_core import QUOTA
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.themes import CAPABILITY as THEMES
from portalab.capabilities.user_grants import CAPABILITY as USER_GRANTS
from portalab.core.permissions import PermissionRegistry

OWNER = "module:marketplace"
NOT_REFUNDABLE = frozenset({"plugin", "access", "quota"})


def _port(capabilities: CapabilityRegistry, name: str) -> Any | None:
    providers = capabilities.system_providers(name)
    return providers[0].provider if providers else None


class Owned:
    """Ownership is the whole effect (read through ``marketplace.entitlements``)."""

    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        return ActivationResult("active")

    async def deactivate(self, ownership: OwnershipView) -> None:
        return None


class WidgetHandler(Owned):
    def __init__(self, widgets: WidgetRegistry) -> None:
        self.widgets = widgets

    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        key = str(ownership.payload.get("widget", ""))
        if self.widgets.get(key) is None:
            return ActivationResult("incompatible", "unknown widget")
        return ActivationResult("active")


class ThemeHandler(Owned):
    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities

    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        catalog = _port(self.capabilities, THEMES)
        if catalog is None:
            return ActivationResult("failed", "themes unavailable")
        if str(ownership.payload.get("theme", "")) not in await catalog.allowed_keys():
            return ActivationResult("incompatible", "unknown theme")
        return ActivationResult("active")


class ExtensionHandler(Owned):
    """``feature``/``plugin``: needs the owner's configuration when the product says so (023 later)."""

    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        if ownership.payload.get("config_required") and not ownership.configuration:
            return ActivationResult("needs_configuration")
        return ActivationResult("active")


class AccessHandler(Owned):
    def __init__(
        self, capabilities: CapabilityRegistry, permissions: PermissionRegistry, config: Callable[[], Any]
    ) -> None:
        self.capabilities = capabilities
        self.permissions = permissions
        self.config = config

    def _permission(self, ownership: OwnershipView) -> str | None:
        key = str(ownership.payload.get("permission", ""))
        declared = self.permissions.get(key)
        if declared is None or declared.reserved or key not in self.config().access_allowed_permissions:
            return None
        return key

    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        key = self._permission(ownership)
        grants = _port(self.capabilities, USER_GRANTS)
        if key is None:
            return ActivationResult("incompatible", "permission not allowed")
        if grants is None:
            return ActivationResult("failed", "grants unavailable")
        await grants.grant(ownership.user_id, key, source=f"marketplace:{ownership.id}")
        return ActivationResult("active")

    async def deactivate(self, ownership: OwnershipView) -> None:
        key = str(ownership.payload.get("permission", ""))
        grants = _port(self.capabilities, USER_GRANTS)
        if grants is not None and key:
            await grants.revoke(ownership.user_id, key)


class QuotaHandler(Owned):
    def __init__(self, capabilities: CapabilityRegistry, config: Callable[[], Any]) -> None:
        self.capabilities = capabilities
        self.config = config

    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        kind = str(ownership.payload.get("kind", ""))
        units = int(ownership.payload.get("units", 0) or 0)
        if kind not in self.config().quota_kinds or units <= 0:
            return ActivationResult("incompatible", "unknown quota")
        quota = _port(self.capabilities, QUOTA)
        if quota is None:
            return ActivationResult("failed", "quota unavailable")
        await quota.add_units(
            ownership.user_id, units, f"marketplace:{ownership.id}", f"marketplace:{ownership.id}"
        )
        return ActivationResult("active")

    async def give_back(self, ownership: OwnershipView) -> bool:
        """Remove the credited units for a refund; False when some were already consumed."""
        units = int(ownership.payload.get("units", 0) or 0)
        quota = _port(self.capabilities, QUOTA)
        if quota is None:
            return False
        available = await quota.available(ownership.user_id)
        if int(available.get("extra_units", 0)) < units:
            return False  # some purchased units were already used: not refundable
        await quota.remove_units(
            ownership.user_id, units, f"marketplace:{ownership.id}", f"marketplace-refund:{ownership.id}"
        )
        return True


def register_builtin_types(
    registry: ProductTypeRegistry,
    capabilities: CapabilityRegistry,
    widgets: WidgetRegistry,
    permissions: PermissionRegistry,
    config: Callable[[], Any],
) -> None:
    owned = Owned()
    for key, handler, fields in (
        ("widget", WidgetHandler(widgets), ("widget",)),
        ("theme", ThemeHandler(capabilities), ("theme",)),
        ("statistic", owned, ("statistic",)),
        ("badge", owned, ("label", "icon")),
        ("title", owned, ("label",)),
        ("effect", owned, ("effect",)),
        ("feature", ExtensionHandler(), ("extension", "config_required")),
        ("plugin", ExtensionHandler(), ("extension", "config_required")),
        ("access", AccessHandler(capabilities, permissions, config), ("permission",)),
        ("quota", QuotaHandler(capabilities, config), ("kind", "units")),
    ):
        if registry.get(key) is None:
            registry.register(
                ProductType(
                    key,
                    OWNER,
                    handler,
                    refundable_by_default=key not in NOT_REFUNDABLE,
                    payload_fields=fields,
                    label_key=f"marketplace:type.{key}",
                )
            )
