"""Event contracts (spec 007): event-type registry, consumers and the delivered envelope.

Producers register the types they emit (``register_event_type``) next to their code; the Events module
validates every publication against this registry, derives deduplication keys from the declared fields
(never a timestamp alone, CD-012) and fans events out to registered consumers (``register_consumer``).
Registrations are owner-tagged so a disabled plugin's contributions disappear (F20).
"""

import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel

from portalab.capabilities.registry import CapabilitySpec
from portalab.core.privacy_registry import looks_personal

RetentionClass = Literal["business", "technical"]
VisibilityClass = Literal["public", "community", "private", "restricted"]
ActorKind = Literal["user", "system", "ai", "automation", "plugin"]

_NAME = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


class EventTypeError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class EventType:
    """A registered event type.

    * ``schema`` validates the payload (a Pydantic model); ``open_payload`` accepts extra fields (still
      checked for secret-like or personal-looking keys);
    * ``dedup_fields``: payload fields whose values identify one logical occurrence; with
      ``source_id_reliable`` the ``(source, source_event_id)`` pair is used instead;
    * ``rewardable`` / ``aggregatable``: per-field annotations consumed by 013 / 017; ``automatable``: 019
      may trigger on it; ``live_permission``: also pushed to the SSE stream for holders of that permission
      (``private`` types go to their subject user only).
    """

    name: str
    owner: str
    version: int = 1
    schema: type[BaseModel] | None = None
    open_payload: bool = True
    dedup_fields: tuple[str, ...] = ()
    source_id_reliable: bool = False
    retention_class: RetentionClass = "business"
    visibility_class: VisibilityClass = "private"
    rewardable: frozenset[str] = frozenset()
    aggregatable: frozenset[str] = frozenset()
    automatable: bool = False
    live_permission: str | None = None
    description: str = ""


class EventTypeRegistry:
    def __init__(self) -> None:
        self._types: dict[str, EventType] = {}

    def register(self, event_type: EventType) -> EventType:
        if not _NAME.fullmatch(event_type.name):
            raise EventTypeError(f"event type {event_type.name!r} must look like '<domain>.<action>'")
        if event_type.version < 1:
            raise EventTypeError("event type versions start at 1")
        if event_type.schema is not None:
            for name in event_type.schema.model_fields:
                if looks_personal(name):
                    raise EventTypeError(f"{event_type.name}.{name}: payloads carry ids, never personal data")
        if event_type.schema is not None:
            annotated = set(event_type.dedup_fields) | event_type.rewardable | event_type.aggregatable
            unknown = annotated - set(event_type.schema.model_fields)
            if unknown:
                raise EventTypeError(f"{event_type.name}: annotations on undeclared fields {sorted(unknown)}")
        existing = self._types.get(event_type.name)
        if existing is not None and existing != event_type:
            raise EventTypeError(f"event type {event_type.name!r} is already registered differently")
        self._types[event_type.name] = event_type
        return event_type

    def get(self, name: str) -> EventType | None:
        return self._types.get(name)

    def all(self) -> list[EventType]:
        return [self._types[name] for name in sorted(self._types)]

    def unregister(self, owner: str) -> int:
        doomed = [name for name, item in self._types.items() if item.owner == owner]
        for name in doomed:
            del self._types[name]
        return len(doomed)


default_event_types = EventTypeRegistry()


def register_event_types(owner: str, *names: str, **options: Any) -> None:
    """Shortcut for producers with open payloads: ``register_event_types("module:x", "x.done", ...)``."""
    for name in names:
        default_event_types.register(EventType(name=name, owner=owner, **options))


# --- delivery ------------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Envelope:
    event_id: UUID
    seq: int
    type: str
    type_version: int
    occurred_at: datetime
    received_at: datetime
    source_system: str
    source_event_id: str | None
    actor_user_id: UUID | None
    actor_kind: str
    subject_type: str | None
    subject_id: str | None
    payload: Mapping[str, Any]
    provenance: Mapping[str, Any]
    correlation_id: str | None


class ConsumerContext(Protocol):
    replay: bool
    as_of: datetime

    async def idempotent_effect(self, key: str) -> bool:
        """True the first time ``key`` is seen for this consumer; False on redelivery."""
        ...


Handler = Callable[[Envelope, ConsumerContext], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class Consumer:
    name: str
    types: frozenset[str]
    handler: Handler = field(compare=False)
    owner: str
    replay_safe: bool = False
    supported_versions: Mapping[str, int] = field(default_factory=dict)  # type → highest version understood


class ConsumerRegistry:
    def __init__(self) -> None:
        self._consumers: dict[str, Consumer] = {}

    def register(self, consumer: Consumer) -> Consumer:
        if consumer.name in self._consumers:
            raise EventTypeError(f"consumer {consumer.name!r} is already registered")
        self._consumers[consumer.name] = consumer
        return consumer

    def get(self, name: str) -> Consumer | None:
        return self._consumers.get(name)

    def replace(self, consumer: Consumer) -> Consumer:
        """Register or swap a consumer by name (projections whose definition changed); its cursor is kept."""
        self._consumers[consumer.name] = consumer
        return consumer

    def remove(self, name: str) -> bool:
        return self._consumers.pop(name, None) is not None

    def all(self) -> list[Consumer]:
        return [self._consumers[name] for name in sorted(self._consumers)]

    def unregister(self, owner: str) -> int:
        doomed = [name for name, item in self._consumers.items() if item.owner == owner]
        for name in doomed:
            del self._consumers[name]
        return len(doomed)


default_consumers = ConsumerRegistry()


def consumer(
    name: str, *, types: set[str] | frozenset[str], owner: str, replay_safe: bool = False
) -> Callable[[Handler], Handler]:
    """Decorator registering a consumer in the default registry."""

    def decorate(handler: Handler) -> Handler:
        default_consumers.register(Consumer(name, frozenset(types), handler, owner, replay_safe))
        return handler

    return decorate


# --- operational statistics (consumed by Observability 025) --------------------------------------------
STATS_CAPABILITY = "events.stats"


@dataclass(frozen=True, slots=True)
class EventStatsSnapshot:
    head_seq: int
    lag_by_consumer: Mapping[str, int]
    dead_letters: int
    failed_deliveries: int
    quarantined: int
    oldest_failure_age_seconds: float | None


@runtime_checkable
class EventStats(Protocol):
    async def snapshot(self) -> EventStatsSnapshot: ...


STATS_SPEC = CapabilitySpec(
    name=STATS_CAPABILITY,
    version="1.0",
    protocol=EventStats,
    multi_provider=False,
    description="Event pipeline statistics: consumer lag, dead letters, quarantine (007).",
)
