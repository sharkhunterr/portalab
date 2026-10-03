"""``service.status_changed`` — one event type shared by Connectors (005, ``dimension="connection"``:
configured/enabled/disabled/…) and Health (006, ``dimension="health"``: operational/degraded/…).

Both specs name the same event (CD canonical event names); the ``dimension`` keeps the two state machines
apart and is part of the deduplication key ``(service_id, dimension, to_state, state_seq)``.
"""

from typing import Literal

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry, default_event_types

STATUS_CHANGED = "service.status_changed"
OWNER = "core:services"


class ServiceStatus(BaseModel):
    service_id: str
    dimension: Literal["connection", "health"] = "connection"
    connector: str | None = None
    from_state: str | None = None
    to_state: str
    state_seq: int
    reason: str | None = None


STATUS_CHANGED_TYPE = EventType(
    name=STATUS_CHANGED,
    owner=OWNER,
    schema=ServiceStatus,
    open_payload=False,
    dedup_fields=("service_id", "dimension", "to_state", "state_seq"),
    retention_class="technical",
    visibility_class="restricted",
    automatable=True,
    live_permission="services.read",
    aggregatable=frozenset({"service_id", "dimension", "connector", "to_state"}),
    description="A service changed state (connection lifecycle or derived health).",
)


def register_status_changed(registry: EventTypeRegistry = default_event_types) -> None:
    registry.register(STATUS_CHANGED_TYPE)


register_status_changed()
