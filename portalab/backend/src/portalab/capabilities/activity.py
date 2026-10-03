"""``activity.attributes`` (spec 014 contract, provided by domains such as Media 024): normalized
attributes of a domain event (media kind, canonical genres, title…) used by campaign (014) and
automation (019) conditions, so those engines never parse domain payloads themselves."""

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from portalab.capabilities.registry import CapabilitySpec

CAPABILITY = "activity.attributes"


@dataclass(frozen=True, slots=True)
class ActivityAttributes:
    media_kind: str | None = None
    genres: tuple[str, ...] = ()
    title: str | None = None
    original_title: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ActivityAttributeProvider(Protocol):
    def handles(self, event_type: str) -> bool: ...

    async def attributes(self, event_type: str, payload: dict[str, Any]) -> ActivityAttributes | None:
        """Attributes of one event, or ``None`` when unavailable (the condition then does not match)."""
        ...


SPEC = CapabilitySpec(
    name=CAPABILITY,
    version="1.0",
    protocol=ActivityAttributeProvider,
    multi_provider=True,
    description="Normalized attributes of domain events for campaign/automation conditions",
)
