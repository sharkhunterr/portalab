"""Connectors settings (T002), declared to Administration (CD-011).

Per-field source priorities are *not* a connectors setting: the reconciler reads the shape owned by the
consuming domain, ``media.fieldPriority.<kind>.<field>`` (spec 024, CD-026, F7).
"""

from dataclasses import dataclass

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:connectors"


@dataclass(frozen=True, slots=True)
class ConnectorsConfig:
    default_sync_interval_seconds: int = 3600
    circuit_failure_threshold: int = 5
    circuit_open_seconds: int = 60
    http_timeout_seconds: float = 10.0
    http_max_response_bytes: int = 5 * 1024 * 1024
    http_retries: int = 2
    resync_confirm_delete_ratio: float = 0.2
    sync_batch_size: int = 200


SETTINGS: dict[str, str] = {
    "default_sync_interval_seconds": "connectors.defaultSyncIntervalSeconds",
    "circuit_failure_threshold": "connectors.circuit.failureThreshold",
    "circuit_open_seconds": "connectors.circuit.openSeconds",
    "http_timeout_seconds": "connectors.http.timeoutSeconds",
    "http_max_response_bytes": "connectors.http.maxResponseBytes",
    "http_retries": "connectors.http.retries",
    "resync_confirm_delete_ratio": "connectors.resync.confirmDeleteRatio",
}

_DESCRIPTIONS = {
    "default_sync_interval_seconds": "Seconds between scheduled syncs of a service (unless overridden).",
    "circuit_failure_threshold": "Consecutive failures that open a service's circuit breaker.",
    "circuit_open_seconds": "Seconds a circuit stays open before a half-open probe.",
    "http_timeout_seconds": "Timeout (s) of one connector HTTP call.",
    "http_max_response_bytes": "Largest accepted connector HTTP response.",
    "http_retries": "Retries of an idempotent connector HTTP call.",
    "resync_confirm_delete_ratio": "Share of a service's records a full resync may deactivate unconfirmed.",
}


def declare_connectors_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {declaration.key for declaration in catalog.all()}
    defaults = ConnectorsConfig()
    for field, key in SETTINGS.items():
        if key in known:
            continue
        default = getattr(defaults, field)
        declare(
            scope="global",
            key=key,
            schema=type(default),
            default=default,
            owner=OWNER,
            description=_DESCRIPTIONS[field],
        )


declare_connectors_settings()
