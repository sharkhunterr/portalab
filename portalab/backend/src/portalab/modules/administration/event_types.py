"""Event types emitted by administration (spec 020, registered for spec 007)."""

from portalab.capabilities.events import register_event_types

OWNER = "module:administration"

register_event_types(
    OWNER,
    "admin.config_changed",
    "admin.policy_changed",
    "admin.module_toggled",
    "admin.plugin_toggled",
    "admin.connector_toggled",
    "admin.service_toggled",
    "admin.automation_toggled",
    "admin.firstrun_completed",
    "admin.import_performed",
    "admin.export_performed",
    retention_class="business",
    visibility_class="restricted",
)
