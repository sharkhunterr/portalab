"""Event types emitted by identity (spec 002, registered for the Events module, spec 007)."""

from portalab.capabilities.events import register_event_types

OWNER = "module:identity"

register_event_types(
    OWNER,
    "user.created",
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
    "user.onboarding_step_completed",  # 027: one step of the welcome (its ``step``) — discovery missions
    "user.tour_completed",  # #7: a guided tour seen to its end (its ``tour``), once — discovery missions
    "user.password_changed",  # issue 407: by the member (« self ») or an administrator (« admin »)
    "user.sso_linked",  # issue 407: a provider account now signs in as this member
    retention_class="business",
    visibility_class="private",
)
register_event_types(  # automations may welcome newly verified members (019)
    OWNER, "user.verified", retention_class="business", visibility_class="private", automatable=True
)
register_event_types(
    OWNER, "user.signed_in", "user.signed_out", retention_class="technical", visibility_class="private"
)
register_event_types(  # 027: came today (once a day, a session kept open included) — daily quests
    OWNER, "user.visited", retention_class="technical", visibility_class="private"
)
