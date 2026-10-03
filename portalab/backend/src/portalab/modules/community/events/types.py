"""Community event types (T003; via 007, ids only): ``community.event_created|updated|cancelled`` —
automatable (019 announcements react to them)."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:community"
TYPES = ("community.event_created", "community.event_updated", "community.event_cancelled")


class CommunityEventChanged(BaseModel):
    event: str
    version: int


def register_event_types(registry: EventTypeRegistry) -> None:
    for name in TYPES:
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=CommunityEventChanged,
                    open_payload=False,
                    dedup_fields=("event", "version"),
                    automatable=True,
                    visibility_class="community",
                )
            )
