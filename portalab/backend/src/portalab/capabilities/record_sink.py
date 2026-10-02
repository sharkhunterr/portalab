"""``RecordSink`` contract (spec 005 T024, R2/R3) and the field-priority reconciler (CD-026, F7).

Consuming modules (e.g. Media 024) register a sink per capability; the sync runner hands it normalized
records. Sinks upsert idempotently by ``(source_system, external_id)``, deactivate removed records, keep
provenance and **never delete** (a purge is the separate, authorized 021 action).
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.connector_sdk import SourceRecord


@dataclass(frozen=True, slots=True)
class ServiceRef:
    service_id: UUID
    source_system: str  # e.g. "plex:<service id>" — provenance of the rows this service owns


@dataclass(frozen=True, slots=True)
class SinkResult:
    added: int = 0
    modified: int = 0
    ignored: int = 0
    errored: int = 0


@runtime_checkable
class RecordSink(Protocol):
    async def upsert(self, records: Sequence[SourceRecord], service: ServiceRef) -> SinkResult: ...

    async def deactivate(self, external_ids: Sequence[str], service: ServiceRef) -> int: ...

    async def active_ids(self, service: ServiceRef) -> set[str]: ...

    async def purge(self, service: ServiceRef) -> int: ...


class SinkRegistry:
    def __init__(self) -> None:
        self._sinks: dict[str, tuple[RecordSink, str]] = {}

    def register(self, capability: str, sink: RecordSink, *, owner: str) -> None:
        if capability in self._sinks:
            raise ValueError(f"a sink is already registered for {capability!r}")
        self._sinks[capability] = (sink, owner)

    def get(self, capability: str) -> RecordSink | None:
        entry = self._sinks.get(capability)
        return entry[0] if entry else None

    def all(self) -> list[tuple[str, RecordSink]]:
        return [(capability, sink) for capability, (sink, _) in sorted(self._sinks.items())]

    def unregister(self, owner: str) -> int:
        doomed = [key for key, (_, who) in self._sinks.items() if who == owner]
        for key in doomed:
            del self._sinks[key]
        return len(doomed)


default_sinks = SinkRegistry()
register_sink: Callable[..., None] = default_sinks.register


@dataclass(frozen=True, slots=True)
class FieldValue:
    value: Any
    source: str


@dataclass
class Reconciled:
    values: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, str] = field(default_factory=dict)


def _matches(source: str, entry: str) -> bool:
    """A priority entry names a connector (``"plex"``) or one service's source (``"plex:<id>"``)."""
    return source == entry or source.split(":", 1)[0] == entry


def reconcile(
    candidates: Mapping[str, Mapping[str, Any]],
    priorities: Mapping[str, Sequence[str]],
    *,
    default_order: Iterable[str] = (),
) -> Reconciled:
    """Merge one item seen by several sources: per field, the first source of its priority list that has a
    value wins (``media.fieldPriority.<kind>.<field>`` tables, CD-026), then ``default_order``, then the
    remaining sources in name order. The winning source of every field is kept as provenance."""
    merged = Reconciled()
    fallback = list(default_order)
    fields = {name for payload in candidates.values() for name in payload}
    for name in sorted(fields):
        order: list[str] = []
        for entry in [*priorities.get(name, ()), *fallback]:
            order.extend(s for s in sorted(candidates) if _matches(s, entry) and s not in order)
        order.extend(s for s in sorted(candidates) if s not in order)
        for source in order:
            value = candidates[source].get(name)
            if value is not None:
                merged.values[name] = value
                merged.provenance[name] = source
                break
    return merged
