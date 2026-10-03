"""Automation settings (T002), declared to Administration."""

from dataclasses import dataclass

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:automations"


@dataclass(frozen=True, slots=True)
class AutomationsConfig:
    enabled: bool = True
    allow_user_authoring: bool = False
    max_steps: int = 10
    max_chain_depth: int = 3
    execution_timeout_seconds: int = 30
    action_timeout_seconds: int = 10
    default_rate_per_minute: int = 60
    global_concurrency: int = 20
    suspend_after_failures: int = 5
    suspend_failure_rate: float = 0.5
    approval_ttl_hours: int = 72
    execution_retention_days: int = 90
    min_schedule_interval_minutes: int = 60


SETTINGS: dict[str, str] = {
    "enabled": "automations.enabled",
    "allow_user_authoring": "automations.allowUserAuthoring",
    "max_steps": "automations.maxSteps",
    "max_chain_depth": "automations.maxChainDepth",
    "execution_timeout_seconds": "automations.executionTimeoutSeconds",
    "action_timeout_seconds": "automations.actionTimeoutSeconds",
    "default_rate_per_minute": "automations.defaultRatePerMinute",
    "global_concurrency": "automations.globalConcurrency",
    "suspend_after_failures": "automations.suspendAfterFailures",
    "suspend_failure_rate": "automations.suspendFailureRate",
    "approval_ttl_hours": "automations.approvalTtlHours",
    "execution_retention_days": "automations.executionRetentionDays",
    "min_schedule_interval_minutes": "automations.minScheduleIntervalMinutes",
}
_DESCRIPTIONS = {
    "enabled": "Run automations (kill switch when off).",
    "allow_user_authoring": "Let users author personal automations (off: Admin only).",
    "max_steps": "Maximum actions in one automation.",
    "max_chain_depth": "Maximum depth of automations triggering automations.",
    "execution_timeout_seconds": "Seconds before an execution is aborted.",
    "action_timeout_seconds": "Seconds before one action is aborted.",
    "default_rate_per_minute": "Executions per automation and minute before batching/throttling.",
    "global_concurrency": "Executions running at once, portal-wide.",
    "suspend_after_failures": "Consecutive failures that suspend an automation.",
    "suspend_failure_rate": "Failure share over the last 20 runs that suspends an automation.",
    "approval_ttl_hours": "Hours an approval request stays open.",
    "execution_retention_days": "Days execution history is kept.",
    "min_schedule_interval_minutes": "Minimum interval between scheduled runs.",
}


def declare_automation_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {d.key for d in catalog.all()}
    defaults = AutomationsConfig()
    for name, key in SETTINGS.items():
        if key not in known:
            default = getattr(defaults, name)
            declare(
                scope="global",
                key=key,
                schema=type(default),
                default=default,
                owner=OWNER,
                description=_DESCRIPTIONS[name],
            )


declare_automation_settings()
