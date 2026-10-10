"""Dashboard events (T020, T026): ``dashboard.layout_changed`` (counts only; dedup per user and layout
version) and ``dashboard.starter_applied`` (dedup per user)."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry

OWNER = "module:dashboard"


class LayoutChanged(BaseModel):
    layout_version: int
    widgets: int
    active: int
    starter: bool = False  # 027: the starter layout being applied (not the member's own doing)


class StarterApplied(BaseModel):
    widgets: int


def register_event_types(registry: EventTypeRegistry) -> None:
    for name, schema in (
        ("dashboard.layout_changed", LayoutChanged),
        ("dashboard.starter_applied", StarterApplied),
    ):
        if registry.get(name) is None:
            registry.register(
                EventType(
                    name=name,
                    owner=OWNER,
                    schema=schema,
                    open_payload=False,
                    retention_class="technical",
                    visibility_class="private",
                    automatable=name == "dashboard.starter_applied",
                )
            )
