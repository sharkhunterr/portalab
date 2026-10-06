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


class TicketChanged(BaseModel):
    ticket: str
    seq: int
    state: str
    type: str
    priority: Literal["low", "normal", "high", "urgent"]


class FeedbackChanged(BaseModel):
    feedback: str
    kind: str
    target: str


TICKET_TYPES = (
    "ticket.created",
    "ticket.updated",
    "ticket.assigned",
    "ticket.state_changed",
    "ticket.reopened",
    "ticket.resolved",
    "ticket.closed",
)


def register_event_types(registry: EventTypeRegistry) -> None:
    for name in TICKET_TYPES:
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=TicketChanged,
                    open_payload=False,
                    dedup_fields=("ticket", "seq"),
                    retention_class="business",
                    visibility_class="private",
                    aggregatable=frozenset({"state", "type", "priority"}),
                    rewardable=frozenset({"type", "priority"}),
                    automatable=True,
                )
            )
    for name in ("feedback.submitted", "feedback.converted"):
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=FeedbackChanged,
                    open_payload=False,
                    dedup_fields=("feedback", "target"),
                    retention_class="business",
                    visibility_class="restricted",
                    aggregatable=frozenset({"kind", "target"}),
                    automatable=True,
                )
            )
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
