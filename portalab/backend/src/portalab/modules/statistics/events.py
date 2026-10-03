"""Statistics events: ``statistics.definition_changed`` (projections refresh), ``statistics.unlocked`` (once
per user and statistic) and ``statistics.wrapped_generated`` (once per recap, period and subject)."""

from typing import Literal

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:statistics"


class DefinitionChanged(BaseModel):
    statistic: str
    version: int
    change: Literal["saved", "activated", "retired"]


class Unlocked(BaseModel):
    statistic: str


class WrappedGenerated(BaseModel):
    recap: str
    period_start: str
    scope: Literal["user", "community"]


def register_event_types(registry: EventTypeRegistry) -> None:
    for name, schema, automatable in (
        ("statistics.definition_changed", DefinitionChanged, False),
        ("statistics.unlocked", Unlocked, True),
        ("statistics.wrapped_generated", WrappedGenerated, True),
    ):
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=schema,
                    open_payload=False,
                    retention_class="technical",
                    visibility_class="private" if name != "statistics.definition_changed" else "restricted",
                    automatable=automatable,
                )
            )
