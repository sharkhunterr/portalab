"""Automation lifecycle events (T003; via 007, ids only): ``automation.created|published|paused|resumed|
suspended|archived``, ``automation.approval_requested|approval_decided`` and the internal
``automation.triggered`` emitted by the ``automation.trigger`` action. Executions are rows, not events."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:automations"
SIGNAL_CHANGED = "service.signal_changed"


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


class SignalChanged(BaseModel):
    """Issue 122: a service's watched data changed (see ``capabilities.service_signals``)."""

    service_id: str
    service_label: str | None = None
    signal: str  # « infrastructure.parity_running »
    label: str | None = None
    value: bool | int | float | str | None = None
    previous: bool | int | float | str | None = None


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
    if registry.get(SIGNAL_CHANGED) is None:
        registry.register(
            EventType(
                name=SIGNAL_CHANGED,
                owner=OWNER,
                schema=SignalChanged,
                open_payload=False,
                retention_class="technical",
                visibility_class="restricted",
                automatable=True,
                description=(
                    "A service's data changed — a parity check started or ended, plays under way, "
                    "container updates… (signal, value, previous, service)."
                ),
            )
        )
