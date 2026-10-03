"""Marketplace event types (T002; via 007, ids and amounts only): ``project.status_changed`` (dedup
``(project, seq)``), ``project.funding_added|funding_released|funding_consumed``."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:marketplace"


class StatusChanged(BaseModel):
    project: str
    proposal: str
    from_state: str | None
    to_state: str
    seq: int


class FundingMoved(BaseModel):
    project: str
    funding: str
    amount: int


def register_event_types(registry: EventTypeRegistry) -> None:
    for name, schema, visibility, aggregatable in (
        ("project.status_changed", StatusChanged, "community", frozenset({"to_state"})),
        ("project.funding_added", FundingMoved, "private", frozenset({"amount"})),
        ("project.funding_released", FundingMoved, "private", frozenset({"amount"})),
        ("project.funding_consumed", FundingMoved, "private", frozenset({"amount"})),
    ):
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=schema,
                    open_payload=False,
                    automatable=True,
                    aggregatable=aggregatable,
                    visibility_class=visibility,  # type: ignore[arg-type]
                )
            )
