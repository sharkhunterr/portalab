"""Incident events (T011): ``incident.created|updated|resolved`` — ids and state only."""

from typing import Literal

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:support"


class IncidentChanged(BaseModel):
    incident_id: str
    update_seq: int
    state: Literal["investigating", "identified", "monitoring", "resolved"]
    severity: Literal["minor", "major", "critical"]
    revision: int


def register_event_types(registry: EventTypeRegistry) -> None:
    for name in ("incident.created", "incident.updated", "incident.resolved"):
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=IncidentChanged,
                    open_payload=False,
                    dedup_fields=("incident_id", "update_seq", "revision"),
                    retention_class="business",
                    visibility_class="community",
                    automatable=True,
                )
            )
