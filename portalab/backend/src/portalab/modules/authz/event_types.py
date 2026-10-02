"""Event types emitted by authorization and the audit store (specs 003/021, registered for spec 007)."""

from portalab.capabilities.events import register_event_types

OWNER = "module:authz"

register_event_types(
    OWNER,
    "permission.role_assigned",
    "permission.role_revoked",
    "permission.group_changed",
    "permission.permission_granted",
    "permission.permission_revoked",
    "permission.policy_changed",
    "permission.admin_transfer_attempted",
    retention_class="business",
    visibility_class="restricted",
)
register_event_types(
    OWNER,
    "permission.denied",
    "audit.checkpoint_created",
    "audit.verification_failed",
    retention_class="technical",
    visibility_class="restricted",
)
