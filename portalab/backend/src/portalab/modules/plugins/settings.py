"""Plugin settings (T002), declared to Administration."""

from dataclasses import dataclass, field

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:plugins"


@dataclass(frozen=True, slots=True)
class PluginsConfig:
    enabled: bool = True
    directory: str = "plugins"
    error_threshold: int = 5  # errors per 10 minutes before quarantine
    hook_timeout_seconds: float = 10.0
    statement_timeout_ms: int = 5000
    update_probation_minutes: int = 10
    require_review: bool = True
    contribution_priority: dict[str, int] = field(default_factory=dict)  # {plugin key: priority}
    # spec 030: confined plugins
    unconfined: str = (
        "existing"  # 023 code in Portalab's process: "existing" (installed before), "allow", "refuse"
    )
    allow_weak_confinement: bool = False
    concurrent_calls: int = 8
    memory_mb: int = 384
    storage_quota_mb: int = 200
    job_timeout_seconds: float = 60.0


SETTINGS: dict[str, str] = {
    "enabled": "plugins.enabled",
    "directory": "plugins.directory",
    "error_threshold": "plugins.errorThreshold",
    "hook_timeout_seconds": "plugins.hookTimeoutSeconds",
    "statement_timeout_ms": "plugins.statementTimeoutMs",
    "update_probation_minutes": "plugins.updateProbationMinutes",
    "require_review": "plugins.requireReview",
    "contribution_priority": "plugins.contributionPriority",
    "unconfined": "plugins.unconfined",
    "allow_weak_confinement": "plugins.allowWeakConfinement",
    "concurrent_calls": "plugins.concurrentCalls",
    "memory_mb": "plugins.memoryMb",
    "storage_quota_mb": "plugins.storageQuotaMb",
    "job_timeout_seconds": "plugins.jobTimeoutSeconds",
}
_DESCRIPTIONS = {
    "enabled": "Load plugins at all (off: the core runs without any plugin).",
    "directory": "Directory holding plugins/available and plugins/installed.",
    "error_threshold": "Plugin errors within 10 minutes before the plugin is quarantined.",
    "hook_timeout_seconds": "Seconds a plugin hook may run before it is cut off.",
    "statement_timeout_ms": "Statement timeout of plugin database sessions (milliseconds).",
    "update_probation_minutes": "Minutes an updated plugin is watched before the update is final.",
    "require_review": "Installing a plugin needs the Admin's review and consent.",
    "contribution_priority": "Priority of each plugin's contributions when they conflict (lower first).",
    "unconfined": "Plugins whose code runs inside Portalab (spec 023): existing (only those installed "
    "before confinement), allow, or refuse.",
    "allow_weak_confinement": "Run confined plugins even where the system cannot fully confine them.",
    "concurrent_calls": "Calls a confined plugin may handle at once.",
    "memory_mb": "Memory of a confined plugin's process (megabytes).",
    "storage_quota_mb": "Default storage quota of a plugin (megabytes).",
    "job_timeout_seconds": "Seconds a confined plugin's job may run.",
}


def declare_plugin_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {d.key for d in catalog.all()}
    defaults = PluginsConfig()
    schemas = {"contribution_priority": dict[str, int]}
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


declare_plugin_settings()
