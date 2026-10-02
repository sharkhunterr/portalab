"""Event types owned by the shell: the ``navigation.contribution_rejected`` diagnostic (technical)."""

from pydantic import BaseModel

from portalab.capabilities.events import EventType, EventTypeRegistry, default_event_types

OWNER = "module:shell"


class ContributionRejected(BaseModel):
    contributor: str
    contribution: str
    reason: str


def register_event_types(registry: EventTypeRegistry = default_event_types) -> None:
    if registry.get("navigation.contribution_rejected") is None:
        registry.register(
            EventType(
                name="navigation.contribution_rejected",
                owner=OWNER,
                schema=ContributionRejected,
                open_payload=False,
                dedup_fields=("contributor", "contribution", "reason"),
                retention_class="technical",
                visibility_class="restricted",
            )
        )
