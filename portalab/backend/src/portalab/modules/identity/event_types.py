"""Event types emitted by identity (spec 002, registered for the Events module, spec 007)."""

from portalab.capabilities.events import register_event_types

OWNER = "module:identity"

register_event_types(
    OWNER,
    "user.created",
    "user.verified",
    "user.profile_updated",
    "user.deactivated",
    "user.reactivated",
    "user.suspended",
    "user.data_export_requested",
    "user.data_exported",
    "user.deletion_requested",
    "user.deletion_cancelled",
    "user.anonymized",
    "user.deleted",
    "user.admin_transferred",
    "user.onboarding_completed",
    retention_class="business",
    visibility_class="private",
)
register_event_types(
    OWNER, "user.signed_in", "user.signed_out", retention_class="technical", visibility_class="private"
)
