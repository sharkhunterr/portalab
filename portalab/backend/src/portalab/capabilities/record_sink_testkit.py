"""Reusable ``RecordSink`` contract kit (spec 005 T022) and an in-memory reference sink.

A consuming module (e.g. Media 024) proves its sink with::

    class TestMediaSink(RecordSinkContractKit):
        async def make_sink(self) -> RecordSink: ...
        async def stored(self, sink, ref) -> dict[str, StoredRecord]: ...   # reads back what the sink kept

The kit checks idempotent upserts keyed by ``(source_system, external_id)``, late/older records not
overwriting newer ones, deactivation instead of deletion, provenance and per-service isolation.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from portalab.capabilities.connector_sdk import SourceRecord
from portalab.capabilities.record_sink import RecordSink, ServiceRef, SinkResult


@dataclass
class StoredRecord:
    external_id: str
    source_system: str
    payload: Mapping[str, Any]
    observed_at: datetime
    active: bool = True
    provenance: Mapping[str, Any] = field(default_factory=dict)


class InMemoryRecordSink:
    """Reference sink: idempotent by ``(source_system, external_id)``; never deletes on its own."""

    def __init__(self, *, fail_on: set[str] | None = None) -> None:
        self.rows: dict[tuple[str, str], StoredRecord] = {}
        self.fail_on = fail_on or set()
        self.calls: list[int] = []

    async def upsert(self, records: Sequence[SourceRecord], service: ServiceRef) -> SinkResult:
        self.calls.append(len(records))
        if any(record.external_id in self.fail_on for record in records):
            raise RuntimeError("sink rejected the batch")
        added = modified = ignored = 0
        for record in records:
            key = (service.source_system, record.external_id)
            current = self.rows.get(key)
            if current is not None and current.observed_at > record.observed_at:
                ignored += 1  # late record: an older observation never overwrites a newer one
                continue
            if current is not None and current.payload == record.payload and current.active:
                ignored += 1
                continue
            self.rows[key] = StoredRecord(
                record.external_id,
                service.source_system,
                dict(record.payload),
                record.observed_at,
                provenance={"service_id": str(service.service_id), "source_system": record.source_system},
            )
            if current is None:
                added += 1
            else:
                modified += 1
        return SinkResult(added=added, modified=modified, ignored=ignored)

    async def deactivate(self, external_ids: Sequence[str], service: ServiceRef) -> int:
        count = 0
        for external_id in external_ids:
            row = self.rows.get((service.source_system, external_id))
            if row is not None and row.active:
                row.active = False
                count += 1
        return count

    async def active_ids(self, service: ServiceRef) -> set[str]:
        return {
            r.external_id for (src, _), r in self.rows.items() if src == service.source_system and r.active
        }

    async def purge(self, service: ServiceRef) -> int:
        doomed = [key for key in self.rows if key[0] == service.source_system]
        for key in doomed:
            del self.rows[key]
        return len(doomed)

    def stored(self, service: ServiceRef) -> dict[str, StoredRecord]:
        return {ext: row for (src, ext), row in self.rows.items() if src == service.source_system}


T0 = datetime(2026, 1, 1, tzinfo=UTC)


def record(external_id: str, *, title: str = "x", at: int = 0, removed: bool = False) -> SourceRecord:
    return SourceRecord(
        source_system="kit",
        external_id=external_id,
        kind="item",
        payload={"title": title},
        observed_at=T0 + timedelta(minutes=at),
        removed=removed,
    )


class RecordSinkContractKit:
    """Subclass and implement ``make_sink`` / ``stored``; every ``test_*`` runs against your sink."""

    async def make_sink(self) -> RecordSink:
        raise NotImplementedError

    async def stored(self, sink: Any, service: ServiceRef) -> dict[str, StoredRecord]:
        raise NotImplementedError

    def ref(self, n: int = 1) -> ServiceRef:
        service_id = UUID(int=n)
        return ServiceRef(service_id=service_id, source_system=f"kit:{service_id}")

    async def test_upsert_is_idempotent(self) -> None:
        sink, ref = await self.make_sink(), self.ref()
        first = await sink.upsert([record("a"), record("b")], ref)
        again = await sink.upsert([record("a"), record("b")], ref)
        assert (first.added, again.added, again.modified) == (2, 0, 0)
        assert set(await self.stored(sink, ref)) == {"a", "b"}

    async def test_change_is_a_modification(self) -> None:
        sink, ref = await self.make_sink(), self.ref()
        await sink.upsert([record("a")], ref)
        result = await sink.upsert([record("a", title="y", at=1)], ref)
        assert result.modified == 1
        assert (await self.stored(sink, ref))["a"].payload["title"] == "y"

    async def test_late_record_does_not_overwrite(self) -> None:
        sink, ref = await self.make_sink(), self.ref()
        await sink.upsert([record("a", title="new", at=5)], ref)
        await sink.upsert([record("a", title="old", at=1)], ref)
        row = (await self.stored(sink, ref))["a"]
        assert row.payload["title"] == "new" and row.observed_at == T0 + timedelta(minutes=5)

    async def test_deactivate_never_deletes(self) -> None:
        sink, ref = await self.make_sink(), self.ref()
        await sink.upsert([record("a"), record("b")], ref)
        assert await sink.deactivate(["a"], ref) == 1
        rows = await self.stored(sink, ref)
        assert set(rows) == {"a", "b"} and rows["a"].active is False
        assert await sink.active_ids(ref) == {"b"}

    async def test_services_are_isolated(self) -> None:
        sink, one, two = await self.make_sink(), self.ref(1), self.ref(2)
        await sink.upsert([record("a")], one)
        await sink.upsert([record("a")], two)
        await sink.deactivate(["a"], one)
        assert await sink.active_ids(two) == {"a"}
        assert await sink.purge(one) == 1
        assert set(await self.stored(sink, two)) == {"a"}
