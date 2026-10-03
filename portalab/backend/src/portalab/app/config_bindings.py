"""Bind module configuration snapshots to the configuration store (spec 020, CD-011).

Modules read plain dataclasses (``IdentityConfig``, ``PrivacyConfig``, ``AuthzConfig``) whose values come
from their declared keys; this binding refreshes them at start-up and whenever ``admin.config_changed``
touches one of their keys in this process (other processes refresh at start-up and at each periodic run).
"""

from dataclasses import replace
from datetime import timedelta
from typing import Any

from portalab.core.logging import get_logger
from portalab.modules.administration.config.service import ConfigService
from portalab.modules.connectors.settings import SETTINGS as CONNECTORS_FIELDS
from portalab.modules.dashboard.settings import SETTINGS as DASHBOARD_FIELDS
from portalab.modules.health.settings import SETTINGS as HEALTH_FIELDS
from portalab.modules.observability.settings import SETTINGS as OBSERVABILITY_FIELDS
from portalab.modules.search.settings import SETTINGS as SEARCH_FIELDS
from portalab.modules.support.settings import SETTINGS as SUPPORT_FIELDS

log = get_logger("portalab.config")

IDENTITY_FIELDS = {
    "session_idle_minutes": "identity.sessionIdleMinutes",
    "session_absolute_hours": "identity.sessionAbsoluteHours",
    "verification_ttl_hours": "identity.verificationTtlHours",
    "deletion_grace_days": "identity.deletionGraceDays",
    "dormancy_days": "identity.dormancyDays",
    "export_ttl_hours": "identity.exportTtlHours",
    "registration_mode": "identity.registrationMode",
    "password_policy": "identity.passwordPolicy",
    "argon2_params": "identity.argon2Params",
}
PRIVACY_FIELDS = {
    "min_aggregate_size": "privacy.minAggregateSize",
    "audit_retention_months": "privacy.retention.auditMonths",
    "export_ttl_days": "privacy.exportTtlDays",
}
AUTHZ_FIELDS = {
    "confirmation_ttl_seconds": "authz.confirmationTtlSeconds",
    "audit_context_max_bytes": "authz.auditContextMaxBytes",
}


async def _values(config: ConfigService, fields: dict[str, str]) -> dict[str, Any]:
    return {field: (await config.get(key)).value for field, key in fields.items()}


async def refresh(platform: Any) -> None:
    config: ConfigService = platform.administration.config
    identity = platform.identity.ctx
    identity.config = replace(identity.config, **await _values(config, IDENTITY_FIELDS))

    privacy = platform.privacy
    retention = dict(privacy.config.retention_days)
    for data_class in list(retention):
        retention[data_class] = (await config.get(f"privacy.retention.{data_class}.days")).value
    privacy_config = replace(
        privacy.config, retention_days=retention, **await _values(config, PRIVACY_FIELDS)
    )
    privacy.config = privacy_config
    privacy.visibility.config = privacy_config
    privacy.retention.config = privacy_config
    privacy.center.config = privacy_config
    privacy.guard.min_size = privacy_config.min_aggregate_size

    authz = platform.authz
    authz.config = replace(authz.config, **await _values(config, AUTHZ_FIELDS))
    authz.confirmations.ttl = timedelta(seconds=authz.config.confirmation_ttl_seconds)
    authz.audit.max_context_bytes = authz.config.audit_context_max_bytes

    connectors = getattr(platform, "connectors", None)
    if connectors is not None:
        connectors.config = replace(connectors.config, **await _values(config, CONNECTORS_FIELDS))
    health = getattr(platform, "health", None)
    if health is not None:
        health.config = replace(health.config, **await _values(config, HEALTH_FIELDS))
    observability = getattr(platform, "observability", None)
    if observability is not None:
        observability.config = replace(observability.config, **await _values(config, OBSERVABILITY_FIELDS))
    dashboard = getattr(platform, "dashboard", None)
    if dashboard is not None:
        dashboard.config = replace(dashboard.config, **await _values(config, DASHBOARD_FIELDS))
    support = getattr(platform, "support", None)
    if support is not None:
        support.config = replace(support.config, **await _values(config, SUPPORT_FIELDS))
    search = getattr(platform, "search", None)
    if search is not None:
        search.config = replace(search.config, **await _values(config, SEARCH_FIELDS))


async def safe_refresh(platform: Any) -> bool:
    """Refresh, tolerating an unmigrated or unreachable database (code defaults stay in force)."""
    try:
        await refresh(platform)
    except Exception:
        log.warning("configuration snapshot not refreshed; code defaults stay in force")
        return False
    return True


def bind(platform: Any) -> None:
    async def on_change(keys: set[str]) -> None:
        await safe_refresh(platform)

    for prefix in (
        "identity.",
        "privacy.",
        "authz.",
        "connectors.",
        "health.",
        "observability.",
        "search.",
        "dashboard.",
        "support.",
    ):
        platform.administration.config.on_change(prefix, on_change)
