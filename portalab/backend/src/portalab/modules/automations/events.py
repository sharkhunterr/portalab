"""Automation lifecycle events (T003; via 007, ids only): ``automation.created|published|paused|resumed|
suspended|archived``, ``automation.approval_requested|approval_decided`` and the internal
``automation.triggered`` emitted by the ``automation.trigger`` action. Executions are rows, not events."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:automations"


class AutomationRef(BaseModel):
    automation: str
    version: int | None = None
    reason: str | None = None


class ApprovalRef(BaseModel):
    automation: str
    action: str
    decision: str | None = None


class Triggered(BaseModel):
    automation: str
    payload: str | None = None


def register_event_types(registry: EventTypeRegistry) -> None:
    for name, schema, automatable in (
        ("automation.created", AutomationRef, False),
        ("automation.published", AutomationRef, False),
        ("automation.paused", AutomationRef, False),
        ("automation.resumed", AutomationRef, False),
        ("automation.suspended", AutomationRef, False),
        ("automation.archived", AutomationRef, False),
        ("automation.approval_requested", ApprovalRef, False),
        ("automation.approval_decided", ApprovalRef, False),
        ("automation.triggered", Triggered, True),
    ):
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=schema,
                    open_payload=False,
                    retention_class="technical",
                    visibility_class="restricted",
                    automatable=automatable,
                )
            )
