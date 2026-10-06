"""Notification settings (T002), declared to Administration (CD-011). Per-user preferences are one
user-overridable setting ``notifications.preferences`` (``{category: {channel: bool}}``) constrained by
the category declarations and the admin category policy."""

from dataclasses import dataclass, field
from typing import Any

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:notifications"
PREFERENCES = "notifications.preferences"
DIGEST = "notifications.email.digest"
CATEGORY_POLICY = "notifications.categoryPolicy"
SMTP_PASSWORD = "notifications.email.smtp.password"  # noqa: S105 — a setting key, not a password


@dataclass(frozen=True, slots=True)
class NotificationsConfig:
    coalesce_window_seconds: int = 120
    retention_days: int = 90
    email_enabled: bool = False
    email_from: str = "portalab@localhost"
    portal_url: str = ""
    smtp_host: str = "localhost"
    smtp_port: int = 25
    smtp_tls: bool = False
    smtp_username: str = ""
    email_max_attempts: int = 5
    digest_default_mode: str = "off"
    category_policy: dict[str, dict[str, Any]] = field(default_factory=dict)


SETTINGS: dict[str, str] = {
    "coalesce_window_seconds": "notifications.coalesceWindowSeconds",
    "retention_days": "notifications.retentionDays",
    "email_enabled": "notifications.email.enabled",
    "email_from": "notifications.email.from",
    "portal_url": "notifications.email.portalUrl",
    "smtp_host": "notifications.email.smtp.host",
    "smtp_port": "notifications.email.smtp.port",
    "smtp_tls": "notifications.email.smtp.tls",
    "smtp_username": "notifications.email.smtp.username",
    "email_max_attempts": "notifications.email.maxAttempts",
    "digest_default_mode": "notifications.digest.defaultMode",
    "category_policy": CATEGORY_POLICY,
}

_DESCRIPTIONS = {
    "coalesce_window_seconds": "Seconds during which repeats about one subject merge into one item.",
    "retention_days": "Days notifications are kept in the notification center.",
    "email_enabled": "Send e-mail notifications (SMTP).",
    "email_from": "Sender address of e-mails.",
    "portal_url": "Public address of the portal, for the links of e-mails (e.g. https://portal.example).",
    "smtp_host": "SMTP server host.",
    "smtp_port": "SMTP server port.",
    "smtp_tls": "Use TLS with the SMTP server.",
    "smtp_username": "SMTP user name (empty: no authentication).",
    "email_max_attempts": "Attempts before an e-mail delivery is marked failed.",
    "digest_default_mode": "Default e-mail digest: off, daily or weekly.",
    "category_policy": "Per-category policy: {category: {mandatory_channels?, disabled_channels?, locked?}}.",
}


def declare_notification_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {declaration.key for declaration in catalog.all()}
    defaults = NotificationsConfig()
    schemas: dict[str, Any] = {"category_policy": dict[str, dict[str, Any]]}
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
    if SMTP_PASSWORD not in known:
        declare(
            scope="global",
            key=SMTP_PASSWORD,
            schema=str | None,
            default=None,
            sensitive=True,
            owner=OWNER,
            description="SMTP password (secret).",
        )
    if PREFERENCES not in known:
        declare(
            scope="global",
            key=PREFERENCES,
            schema=dict[str, dict[str, bool]],
            default={},
            user_overridable=True,
            owner=OWNER,
            description="My notification channels per category.",
        )
    if DIGEST not in known:
        declare(
            scope="global",
            key=DIGEST,
            schema=str,
            default="off",
            user_overridable=True,
            owner=OWNER,
            description="My e-mail digest: off, daily or weekly.",
        )


declare_notification_settings()
