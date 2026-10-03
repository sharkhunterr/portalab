"""Calendar events: ``calendar.reminder_sent`` (dedup per reminder; subject = the user, private)."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:calendar"


class ReminderSent(BaseModel):
    reminder: str
    source: str


def register_event_types(registry: EventTypeRegistry) -> None:
    if registry.get("calendar.reminder_sent") is None:
        registry.register(
            EventType(
                name="calendar.reminder_sent",
                owner=OWNER,
                schema=ReminderSent,
                open_payload=False,
                dedup_fields=("reminder",),
                retention_class="technical",
                visibility_class="private",
            )
        )
