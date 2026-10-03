"""Notification events: ``notification.sent`` (communication-level counts), ``notification.read`` (user
level, dedup per notification) and ``notification.delivery_failed`` (diagnostic, per channel and minute).
Ids and counts only — never titles, bodies or addresses."""

from typing import Literal

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:notifications"


class Sent(BaseModel):
    communication: str
    category: str
    kind: str
    recipients: int


class Read(BaseModel):
    notification: str


class DeliveryFailed(BaseModel):
    channel: str
    minute: str


def register_event_types(registry: EventTypeRegistry) -> None:
    visibility: Literal["public", "community", "private", "restricted"]
    for name, schema, visibility in (
        ("notification.sent", Sent, "restricted"),
        ("notification.read", Read, "private"),
        ("notification.delivery_failed", DeliveryFailed, "restricted"),
    ):
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=schema,
                    open_payload=False,
                    retention_class="technical",
                    visibility_class=visibility,
                )
            )
