"""005 T022 — the reusable RecordSink contract kit, run against the in-memory reference sink."""

from typing import Any

from portalab.capabilities.record_sink import RecordSink, ServiceRef
from portalab.capabilities.record_sink_testkit import InMemoryRecordSink, RecordSinkContractKit, StoredRecord


class TestReferenceSink(RecordSinkContractKit):
    async def make_sink(self) -> RecordSink:
        return InMemoryRecordSink()

    async def stored(self, sink: Any, service: ServiceRef) -> dict[str, StoredRecord]:
        return dict(sink.stored(service))
