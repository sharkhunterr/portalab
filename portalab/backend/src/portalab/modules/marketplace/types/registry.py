"""Baseline product types (T020, T026; R7, R10): ``widget``, ``theme``, ``statistic`` (read by 009, 022 and
017 through ``marketplace.entitlements``), cosmetic ``badge``/``title``/``effect`` (shown in profiles),
``feature``/``plugin`` (portal-level code is installed by the Admin when publishing — ownership is per
user; 023 activation is a stub until step 27), ``access`` (a scoped grant limited to the Admin allow-list,
never an Admin-reserved permission, removed on revoke) and ``quota`` (units credited by Media's
``RequestQuotaService``; Marketplace never measures nor consumes quota, never sells priority)."""

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from portalab.capabilities.dashboard import WidgetRegistry
from portalab.capabilities.marketplace import (
    ActivationResult,
    OwnershipView,
    ProductType,
    ProductTypeRegistry,
)
from portalab.capabilities.media_core import QUOTA
from portalab.capabilities.plugins import EXTENSION_ACTIVATION
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.themes import CAPABILITY as THEMES
from portalab.capabilities.user_grants import CAPABILITY as USER_GRANTS
from portalab.core.permissions import PermissionRegistry

OWNER = "module:marketplace"
NOT_REFUNDABLE = frozenset({"plugin", "access", "quota", "bundle", "project_launch"})


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
    """``feature``/``plugin``: needs the owner's configuration when the product says so; a plugin product
    is activated for its owner through 023's ``ExtensionActivation`` (grants ``plugin:<key>.use``)."""

    def __init__(self, capabilities: CapabilityRegistry | None = None) -> None:
        self.capabilities = capabilities

    def _activation(self) -> Any | None:
        return _port(self.capabilities, EXTENSION_ACTIVATION) if self.capabilities is not None else None

    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        if ownership.payload.get("config_required") and not ownership.configuration:
            return ActivationResult("needs_configuration")
        activation = self._activation()
        extension = str(ownership.payload.get("extension", ""))
        if activation is None or not extension:
            return ActivationResult("active")
        status = await activation.activate_for_user(extension, ownership.user_id)
        return ActivationResult(status)

    async def deactivate(self, ownership: OwnershipView) -> None:
        activation = self._activation()
        extension = str(ownership.payload.get("extension", ""))
        if activation is not None and extension:
            await activation.deactivate_for_user(extension, ownership.user_id)


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


class BundleHandler(Owned):
    """``bundle`` (027): a pack — buying it grants each product it lists (``payload.products``), one
    already owned staying as it is. A pack is not refundable (its products live on their own)."""

    def __init__(self, grant: Callable[[UUID, str, str], Awaitable[bool]] | None) -> None:
        self.grant = grant

    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        products = [str(p) for p in ownership.payload.get("products") or [] if p]
        if not products:
            return ActivationResult("incompatible", "empty pack")
        if self.grant is None:
            return ActivationResult("failed", "grants unavailable")
        for key in products:
            if key == ownership.product_key:
                continue  # a pack never contains itself
            try:
                await self.grant(ownership.user_id, key, ownership.product_key)
            except Exception:  # noqa: S112 — an unknown product is skipped, the others are granted
                continue
        return ActivationResult("active")


class ProjectLaunchHandler(Owned):
    """``project_launch`` (027): buying it launches a community project for something the member wants —
    they name it and pitch it (the owner's configuration ``title`` and ``pitch``), then it starts as a
    proposal the community funds. Not refundable once launched."""

    def __init__(self, launch: Callable[[UUID, UUID, str, str], Awaitable[None]] | None) -> None:
        self.launch = launch

    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        title = str(ownership.configuration.get("title") or "").strip()
        if not title:
            return ActivationResult("needs_configuration")
        if self.launch is None:
            return ActivationResult("failed", "projects unavailable")
        await self.launch(
            ownership.user_id,
            ownership.id,
            title[:200],
            str(ownership.configuration.get("pitch") or "")[:2000],
        )
        return ActivationResult("active")


def register_builtin_types(
    registry: ProductTypeRegistry,
    capabilities: CapabilityRegistry,
    widgets: WidgetRegistry,
    permissions: PermissionRegistry,
    config: Callable[[], Any],
    *,
    bundle_grant: Callable[[UUID, str, str], Awaitable[bool]] | None = None,
    project_launch: Callable[[UUID, UUID, str, str], Awaitable[None]] | None = None,
) -> None:
    owned = Owned()
    for key, handler, fields in (
        ("widget", WidgetHandler(widgets), ("widget",)),
        ("theme", ThemeHandler(capabilities), ("theme",)),
        ("statistic", owned, ("statistic",)),
        ("badge", owned, ("label", "icon", "style")),  # 027: ``style`` animates it
        ("title", owned, ("label", "style")),
        ("effect", owned, ("effect",)),
        ("feature", ExtensionHandler(), ("extension", "config_required")),
        ("plugin", ExtensionHandler(capabilities), ("extension", "config_required")),
        ("access", AccessHandler(capabilities, permissions, config), ("permission",)),
        ("quota", QuotaHandler(capabilities, config), ("kind", "units")),
        ("notification_style", owned, ("style",)),  # 027: notification looks sold in the shop
        ("notification_animation", owned, ("animation",)),
        ("bundle", BundleHandler(bundle_grant), ("products",)),  # 027: packs
        ("profile_banner", owned, ("banner",)),  # 027: profile cosmetics (Steam-like)
        ("avatar_frame", owned, ("frame",)),
        ("profile_backdrop", owned, ("feature",)),  # unlocks every film backdrop as a banner
        ("palette", owned, ("palette",)),  # colour palettes over the theme
        ("ambient", owned, ("ambient",)),  # an animated layer behind the whole portal
        ("profile_background", owned, ("background",)),  # an animated background behind the profile
        ("name_style", owned, ("style",)),  # the name's font and effect on the profile
        ("level_badge", owned, ("style",)),  # the look of the level (XP) badge
        ("level_up", owned, ("animation",)),  # how a level-up is shown
        ("widget_option", owned, ("option",)),  # a widget setting value: ``<widget>:<field>=<value>``
        ("project_launch", ProjectLaunchHandler(project_launch), ("kind",)),  # a community project
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
