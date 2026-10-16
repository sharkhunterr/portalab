"""Event types emitted by visuals (spec 028, registered for spec 007)."""

from portalab.capabilities.events import register_event_types

OWNER = "module:visuals"

register_event_types(
    OWNER,
    "visuals.pack_changed",  # published, refused, switched on/off, rolled back, archived, removed, purged
    "visuals.element_failed",  # a pack's script that did not answer in members' pages
    retention_class="business",
    visibility_class="restricted",
)
