"""Marketplace settings (T002), declared to Administration."""

from dataclasses import dataclass, field
from typing import Any

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:marketplace"
DEFAULT_RULES: dict[str, Any] = {
    "refund_on_reject": 100,
    "refund_on_abandon": 100,
    "consume_at": "released",
    "min_funding": 1,
    "max_funding_per_user": 1000,
}


@dataclass(frozen=True, slots=True)
class MarketplaceConfig:
    funding_min_amount: int = 1
    funding_max_per_user: int = 10_000
    funding_default_rules: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_RULES))
    access_allowed_permissions: list[str] = field(default_factory=list)
    quota_kinds: list[str] = field(default_factory=lambda: ["media_requests"])
    activation_retry_minutes: int = 15


SETTINGS: dict[str, str] = {
    "funding_min_amount": "marketplace.funding.minAmount",
    "funding_max_per_user": "marketplace.funding.maxPerUser",
    "funding_default_rules": "marketplace.funding.defaultRules",
    "access_allowed_permissions": "marketplace.access.allowedPermissions",
    "quota_kinds": "marketplace.quota.kinds",
    "activation_retry_minutes": "marketplace.activationRetryMinutes",
}
_DESCRIPTIONS = {
    "funding_min_amount": "Smallest Coins amount one funding may reserve.",
    "funding_max_per_user": "Most Coins one member may reserve on one project.",
    "funding_default_rules": "Funding rules proposed when a project opens (refunds, consumption).",
    "access_allowed_permissions": "Permissions an access product may grant (never Admin-reserved ones).",
    "quota_kinds": "Quota kinds products may credit (e.g. media requests).",
    "activation_retry_minutes": "Minutes between retries of a failed product activation.",
}


def declare_marketplace_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {d.key for d in catalog.all()}
    defaults = MarketplaceConfig()
    schemas: dict[str, Any] = {
        "funding_default_rules": dict[str, Any],
        "access_allowed_permissions": list[str],
        "quota_kinds": list[str],
    }
    for name, key in SETTINGS.items():
        if key not in known:
            default = getattr(defaults, name)
            declare(
                scope="global",
                key=key,
                schema=schemas.get(name, type(default)),
                default=default,
                owner=OWNER,
                description=_DESCRIPTIONS[name],
            )


declare_marketplace_settings()
