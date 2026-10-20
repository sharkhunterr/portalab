"""Baseline product types (T020, T026; R7, R10): ``widget``, ``theme``, ``statistic`` (read by 009, 022 and
017 through ``marketplace.entitlements``), cosmetic ``badge``/``title``/``effect`` (shown in profiles),
``feature``/``plugin`` (portal-level code is installed by the Admin when publishing — ownership is per
user; 023 activation is a stub until step 27), ``access`` (a scoped grant limited to the Admin allow-list,
never an Admin-reserved permission, removed on revoke) and ``quota`` (units credited by Media's
``RequestQuotaService``; Marketplace never measures nor consumes quota, never sells priority)."""

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from portalab.capabilities.ai import PERKS as AI_PERKS
from portalab.capabilities.dashboard import WidgetRegistry
from portalab.capabilities.economy import PERKS
from portalab.capabilities.marketplace import (
    ActivationResult,
    OwnershipView,
    ProductType,
    ProductTypeRegistry,
)
from portalab.capabilities.media_core import QUOTA, RESCUES
from portalab.capabilities.plugins import EXTENSION_ACTIVATION
from portalab.capabilities.registry import CapabilityRegistry
from portalab.capabilities.themes import CAPABILITY as THEMES
from portalab.capabilities.user_grants import CAPABILITY as USER_GRANTS
from portalab.core.permissions import PermissionRegistry
from portalab.modules.marketplace.boosters import PAYLOAD_FIELDS

OWNER = "module:marketplace"
# 027: a request (special, service) is settled by the administrators — declined, its Coins come back
NOT_REFUNDABLE = frozenset(
    {
        "plugin",
        "access",
        "quota",
        "bundle",
        "project_launch",
        "special_request",
        "service_access",
        "streak_freeze",
        "xp_boost",
        "media_rescue",
        "booster",
        "early_unlock",  # #131
        "ai_capacity",  # issue 173: spent as soon as the assistant answers
    }
)


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


class SpecialRequestHandler(Owned):
    """``special_request`` (027): something the administrators deliver by hand — a film in 4K with the
    member's wishes. The owner fills the product's form (``payload.form``: title, sound, languages…), then
    a request opens, to be handled within ``payload.deadline_days``."""

    def __init__(self, requests: Any | None) -> None:
        self.requests = requests

    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        from portalab.modules.marketplace.requests.service import answers, form_of

        form = form_of(ownership.payload)
        if form and not ownership.configuration:
            return ActivationResult("needs_configuration")
        if self.requests is None:
            return ActivationResult("failed", "requests unavailable")
        try:
            details = answers(form, ownership.configuration)
        except Exception:
            return ActivationResult("needs_configuration")
        await self.requests.open(ownership, "special", details)
        return ActivationResult("active")

    async def deactivate(self, ownership: OwnershipView) -> None:
        if self.requests is not None:
            await self.requests.close_for(ownership)


class ServiceAccessHandler(Owned):
    """``service_access`` (027): access to a service of the homelab (``payload.service``, joined through the
    identity provider's ``payload.group``). Buying it opens a request; an administrator approves it — and
    Portalab offers to create the account — or declines it (the Coins come back). Revoked, the access is
    withdrawn."""

    def __init__(self, requests: Any | None) -> None:
        self.requests = requests

    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        if self.requests is None:
            return ActivationResult("failed", "requests unavailable")
        details = {
            "service": str(ownership.payload.get("service") or "")[:64],
            "group": str(ownership.payload.get("group") or "")[:120],
        }
        await self.requests.open(ownership, "service", details)
        return ActivationResult("active")

    async def deactivate(self, ownership: OwnershipView) -> None:
        if self.requests is not None:
            await self.requests.close_for(ownership)


class StreakFreezeHandler(Owned):
    """``streak_freeze`` (#54): ``payload.count`` freezes, each covering one missed day of the owner's play
    streak — used automatically by Gamification. Consumed, not refundable (sold ``repeatable``)."""

    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities

    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        count = int(ownership.payload.get("count", 1) or 0)
        if count <= 0:
            return ActivationResult("incompatible", "no freeze")
        perks = _port(self.capabilities, PERKS)
        if perks is None:
            return ActivationResult("failed", "gamification unavailable")
        await perks.grant_freezes(ownership.user_id, min(count, 30), f"marketplace:{ownership.id}")
        return ActivationResult("active")


class RescueHandler(Owned):
    """``media_rescue`` (#57): ``payload.count`` rescues, each saving one title from the cleanup tool's
    deletion — spent by the member on the title's page (Media keeps them). Consumed, not refundable."""

    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities

    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        count = int(ownership.payload.get("count", 1) or 0)
        if count <= 0:
            return ActivationResult("incompatible", "no rescue")
        rescues = _port(self.capabilities, RESCUES)
        if rescues is None:
            return ActivationResult("failed", "media unavailable")
        await rescues.grant(ownership.user_id, min(count, 30), f"marketplace:{ownership.id}")
        return ActivationResult("active")


class BoostHandler(Owned):
    """``xp_boost`` (#55): multiplies the owner's gains (``payload.values``, XP by default) by
    ``payload.factor`` for ``payload.hours`` — after the boost already running, if any. Under the
    economy's global boost cap, like campaigns and streaks."""

    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities

    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        try:
            factor = float(ownership.payload.get("factor", 0) or 0)
            hours = float(ownership.payload.get("hours", 0) or 0)
        except (TypeError, ValueError):
            return ActivationResult("incompatible", "invalid boost")
        values = [str(v) for v in ownership.payload.get("values") or ["xp"] if v in ("xp", "coins")]
        if factor <= 1 or hours <= 0 or not values:
            return ActivationResult("incompatible", "invalid boost")
        perks = _port(self.capabilities, PERKS)
        if perks is None:
            return ActivationResult("failed", "gamification unavailable")
        await perks.grant_boost(ownership.user_id, factor, hours, values, f"marketplace:{ownership.id}")
        return ActivationResult("active")


class BoosterHandler(Owned):
    """``booster`` (#81): owned — bought, or offered (a level reward, an achievement unlocked) — it goes
    sealed into the member's reserve, to be opened when they want (no Coins then). Not refundable."""

    def __init__(self, seal: Callable[[UUID, str, str], Awaitable[None]] | None) -> None:
        self.seal = seal

    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        if self.seal is None:
            return ActivationResult("failed", "boosters unavailable")
        await self.seal(ownership.user_id, ownership.product_key, f"ownership:{ownership.id}")
        return ActivationResult("active")


class EarlyUnlockHandler(BoosterHandler):
    """``early_unlock`` (#131): bought, it goes into the member's reserve — to be spent later on an item they
    hold but may not wear yet for want of a level. Dear and limited (its copies, its purchase limit)."""


class AiCapacityHandler(Owned):
    """``ai_capacity`` (issue 173): a capacity of the assistant — more tokens a day, a recharge, the stronger
    model, more reflection, a longer memory, reserved tools (``perk``, ``amount``, ``hours``). The assistant
    keeps it; one the administrators do not offer is « incompatible ». Withdrawn on a revoke."""

    def __init__(self, capabilities: CapabilityRegistry) -> None:
        self.capabilities = capabilities

    async def activate(self, ownership: OwnershipView) -> ActivationResult:
        perks = _port(self.capabilities, AI_PERKS)
        if perks is None:
            return ActivationResult("failed", "assistant unavailable")
        granted = await perks.grant(
            ownership.user_id,
            str(ownership.payload.get("perk", "")),
            int(ownership.payload.get("amount", 0) or 0),
            int(ownership.payload.get("hours", 0) or 0),
            f"marketplace:{ownership.id}",
        )
        return ActivationResult("active") if granted else ActivationResult("incompatible", "not offered")

    async def deactivate(self, ownership: OwnershipView) -> None:
        perks = _port(self.capabilities, AI_PERKS)
        if perks is not None:
            await perks.revoke(f"marketplace:{ownership.id}")


def register_builtin_types(
    registry: ProductTypeRegistry,
    capabilities: CapabilityRegistry,
    widgets: WidgetRegistry,
    permissions: PermissionRegistry,
    config: Callable[[], Any],
    *,
    bundle_grant: Callable[[UUID, str, str], Awaitable[bool]] | None = None,
    project_launch: Callable[[UUID, UUID, str, str], Awaitable[None]] | None = None,
    requests: Any | None = None,
    booster_seal: Callable[[UUID, str, str], Awaitable[None]] | None = None,
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
        # 027: requests the administrators handle: a special one (a film in 4K…) and a service's access
        ("special_request", SpecialRequestHandler(requests), ("form", "deadline_days")),
        ("service_access", ServiceAccessHandler(requests), ("service", "group", "deadline_days")),
        # #54/#55: consumable perks for the play streak and the gains
        ("streak_freeze", StreakFreezeHandler(capabilities), ("count",)),
        ("xp_boost", BoostHandler(capabilities), ("factor", "hours", "values")),
        # #57: saving a title from the library's cleanup (Maintainerr)
        ("media_rescue", RescueHandler(capabilities), ("count",)),
        # #81: a sealed booster, to open from the reserve
        ("booster", BoosterHandler(booster_seal), PAYLOAD_FIELDS),
        # #131: a pass opening an item waiting for its level, kept in the reserve
        ("early_unlock", EarlyUnlockHandler(booster_seal), ()),
        # issue 173: the assistant's capacities
        ("ai_capacity", AiCapacityHandler(capabilities), ("perk", "amount", "hours")),
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
