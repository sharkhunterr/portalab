"""Privacy and security settings declared to Administration (plan §7, CD-011). Code defaults until the
Configuration step resolves values; thresholds and windows are admin policy, not product rules (R3)."""

from dataclasses import dataclass, field

from portalab.capabilities.visibility import DATA_CLASSES
from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:privacy"

DEFAULT_RETENTION_DAYS: dict[str, int | None] = {
    "personal": None,  # kept while the account exists; erased by the deletion lifecycle
    "activity": None,
    "technical": 30,
    "history": None,
    "audit": None,  # audit retention is by month partitions (auditMonths)
    "aggregate": None,
}


@dataclass(frozen=True, slots=True)
class PrivacyConfig:
    min_aggregate_size: int = 5
    retention_days: dict[str, int | None] = field(default_factory=lambda: dict(DEFAULT_RETENTION_DAYS))
    audit_retention_months: int = 24
    export_ttl_days: int = 7
    default_levels: dict[str, str] = field(default_factory=dict)  # per datum class; fallback: registration


@dataclass(frozen=True, slots=True)
class SecurityConfig:
    max_body_bytes: int = 10 * 1024 * 1024
    rate_limit_per_ip_per_minute: int = 600
    rate_limit_per_user_per_minute: int = 300
    rate_limit_sign_in_per_minute: int = 30  # #276: password and account attempts per address
    # 030 (issue 144): outgoing calls only to known hosts, when switched on
    egress_enabled: bool = False
    egress_hosts: list[str] = field(default_factory=list)


def declare_privacy_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {declaration.key for declaration in catalog.all()}
    privacy, security = PrivacyConfig(), SecurityConfig()
    entries: list[tuple[str, object, object, str]] = [
        ("privacy.minAggregateSize", int, privacy.min_aggregate_size, "Smallest group shown in aggregates."),
        (
            "privacy.retention.auditMonths",
            int,
            privacy.audit_retention_months,
            "Months of audit entries kept.",
        ),
        (
            "privacy.exportTtlDays",
            int,
            privacy.export_ttl_days,
            "Days a personal-data export stays available.",
        ),
        ("security.maxBodyBytes", int, SecurityConfig().max_body_bytes, "Largest accepted request body."),
        (
            "security.rateLimit.perIpPerMinute",
            int,
            security.rate_limit_per_ip_per_minute,
            "Requests per minute per client address.",
        ),
        (
            "security.egress.enabled",
            bool,
            security.egress_enabled,
            "Outgoing calls only to known hosts: configured services, sign-in, pack sources, AI providers, "
            "plugins' accepted hosts and the hosts listed below.",
        ),
        (
            "security.egress.hosts",
            list[str],
            [],
            "More hosts Portalab may call (an asterisk: any subdomain).",
        ),
        (
            "security.rateLimit.perUserPerMinute",
            int,
            security.rate_limit_per_user_per_minute,
            "Requests per minute per signed-in session.",
        ),
    ]
    for data_class in DATA_CLASSES:
        entries.append(
            (
                f"privacy.retention.{data_class}.days",
                int | None,
                DEFAULT_RETENTION_DAYS[data_class],
                f"Days {data_class} data is kept (empty = no time-based cleanup).",
            )
        )
    for key, schema, default, description in entries:
        if key not in known:
            declare(
                scope="global", key=key, schema=schema, default=default, owner=OWNER, description=description
            )


declare_privacy_settings()
