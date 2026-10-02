"""Event types emitted by privacy (spec 021, registered for spec 007)."""

from portalab.capabilities.events import register_event_types

OWNER = "module:privacy"

register_event_types(
    OWNER,
    "privacy.override_applied",
    "privacy.override_removed",
    "service.data_purged",
    retention_class="business",
    visibility_class="restricted",
)
register_event_types(
    OWNER, "privacy.retention_applied", retention_class="technical", visibility_class="restricted"
)
