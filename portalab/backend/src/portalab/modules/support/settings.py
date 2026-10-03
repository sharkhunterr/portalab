"""Support settings (T002), declared to Administration (CD-011). Slice A uses
``support.incident.precheckMatchMode``; the ticket/attachment settings are consumed by Slice B."""

from dataclasses import dataclass, field

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:support"


@dataclass(frozen=True, slots=True)
class SupportConfig:
    attachments_max_bytes: int = 10 * 1024 * 1024
    attachments_max_per_post: int = 5
    attachments_allowed_types: list[str] = field(
        default_factory=lambda: ["image/png", "image/jpeg", "image/webp", "application/pdf", "text/plain"]
    )
    ticket_retention_months: int = 24
    reopen_window_days: int = 14
    draft_ttl_minutes: int = 60
    incident_precheck_match_mode: str = "service_or_text"


SETTINGS: dict[str, str] = {
    "attachments_max_bytes": "support.attachments.maxBytes",
    "attachments_max_per_post": "support.attachments.maxPerPost",
    "attachments_allowed_types": "support.attachments.allowedTypes",
    "ticket_retention_months": "support.ticketRetentionMonths",
    "reopen_window_days": "support.reopenWindowDays",
    "draft_ttl_minutes": "support.draftTtlMinutes",
    "incident_precheck_match_mode": "support.incident.precheckMatchMode",
}

_DESCRIPTIONS = {
    "attachments_max_bytes": "Maximum size of one ticket attachment (bytes).",
    "attachments_max_per_post": "Maximum attachments per ticket or comment.",
    "attachments_allowed_types": "Allowed attachment types (sniffed content type).",
    "ticket_retention_months": "Months closed tickets are kept.",
    "reopen_window_days": "Days during which a resolved ticket can be reopened by its requester.",
    "draft_ttl_minutes": "Minutes a ticket draft (e.g. prefilled by the assistant) is kept.",
    "incident_precheck_match_mode": "How open incidents are matched before a ticket: service, text or both.",
}


def declare_support_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {declaration.key for declaration in catalog.all()}
    defaults = SupportConfig()
    for name, key in SETTINGS.items():
        if key in known:
            continue
        default = getattr(defaults, name)
        schema: object = type(default)
        if name == "attachments_allowed_types":
            schema = list[str]
        declare(
            scope="global",
            key=key,
            schema=schema,
            default=default,
            owner=OWNER,
            description=_DESCRIPTIONS[name],
        )


declare_support_settings()
