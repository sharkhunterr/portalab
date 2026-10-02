"""Event types owned by the Events module itself (registered on import)."""

from portalab.capabilities.events import EventType, default_event_types

OWNER = "module:events"

for _name, _klass in (
    ("events.quarantined", "technical"),
    ("events.consumer_dead_lettered", "technical"),
    ("events.replay_started", "technical"),
    ("events.replay_finished", "technical"),
):
    default_event_types.register(
        EventType(name=_name, owner=OWNER, retention_class=_klass, visibility_class="restricted")  # type: ignore[arg-type]
    )
