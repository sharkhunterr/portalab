"""``support.incidents`` conformance kit and in-memory reference (spec 016 T004/T006). Consumers (006, 025)
test against :class:`InMemoryIncidents`; the real port proves the same contract with::

    class TestRealPort(IncidentsPortContractKit):
        async def make_port(self) -> Incidents: ...

Contract: ``create`` idempotent per ``(source, dedup_key)``; ``attach`` adds evidence to an open incident
and returns ``None`` for an unknown or resolved one; ``link`` makes the incident show in
``open_for_service``; ``get`` returns ``None`` for unknown ids (never raises).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from portalab.capabilities.health import IncidentRef, Incidents


@dataclass
class _Record:
    ref: IncidentRef
    services: set[str] = field(default_factory=set)
    evidence: list[Mapping[str, Any]] = field(default_factory=list)
    resolved: bool = False


class InMemoryIncidents:
    def __init__(self) -> None:
        self.records: dict[str, _Record] = {}
        self.keys: dict[tuple[str, str], str] = {}

    async def create(
        self,
        *,
        title: str,
        source: str,
        severity: str,
        evidence: Mapping[str, Any],
        service_ids: Sequence[str] = (),
        dedup_key: str | None = None,
        summary: str | None = None,
        banner: bool = False,
    ) -> IncidentRef:
        if dedup_key is not None and (source, dedup_key) in self.keys:
            record = self.records[self.keys[(source, dedup_key)]]
            record.services.update(service_ids)
            return record.ref
        ref = IncidentRef(id=str(uuid4()), title=title, status="investigating", opened_at=datetime.now(UTC))
        self.records[ref.id] = _Record(ref, set(service_ids), [dict(evidence)] if evidence else [])
        if dedup_key is not None:
            self.keys[(source, dedup_key)] = ref.id
        return ref

    async def attach(self, incident_id: str, evidence: Mapping[str, Any]) -> IncidentRef | None:
        record = self.records.get(incident_id)
        if record is None or record.resolved:
            return None
        record.evidence.append(dict(evidence))
        return record.ref

    async def link(self, service_id: str, incident_id: str) -> None:
        if incident_id in self.records:
            self.records[incident_id].services.add(service_id)

    async def open_for_service(self, service_id: str) -> list[IncidentRef]:
        return [r.ref for r in self.records.values() if service_id in r.services and not r.resolved]

    async def get(self, incident_id: str) -> IncidentRef | None:
        record = self.records.get(incident_id)
        return record.ref if record else None

    def resolve(self, incident_id: str) -> None:
        record = self.records[incident_id]
        record.resolved = True
        record.ref = replace(record.ref, status="resolved")


class IncidentsPortContractKit:
    async def make_port(self) -> Incidents:
        raise NotImplementedError

    async def resolve(self, port: Any, incident_id: str) -> None:
        """Close an incident through the implementation's own means (staff API, test helper…)."""
        raise NotImplementedError

    async def test_create_is_idempotent(self) -> None:
        port = await self.make_port()
        evidence = {"anomaly_id": "a1"}
        first = await port.create(
            title="DB down", source="observability", severity="critical", evidence=evidence, dedup_key="k1"
        )
        again = await port.create(
            title="DB down (again)",
            source="observability",
            severity="critical",
            evidence=evidence,
            dedup_key="k1",
        )
        other = await port.create(
            title="DB down", source="health", severity="critical", evidence={}, dedup_key="k1"
        )
        assert first.id == again.id and other.id != first.id

    async def test_link_attach_and_open_for_service(self) -> None:
        port = await self.make_port()
        ref = await port.create(
            title="Media slow", source="manual", severity="minor", evidence={}, service_ids=["s1"]
        )
        await port.link("s2", ref.id)
        assert [i.id for i in await port.open_for_service("s2")] == [ref.id]
        assert await port.attach(ref.id, {"evidence_ref": "probe:42"}) is not None
        await self.resolve(port, ref.id)
        assert await port.attach(ref.id, {"evidence_ref": "probe:43"}) is None
        assert await port.open_for_service("s1") == []

    async def test_get_unknown_is_none(self) -> None:
        port = await self.make_port()
        assert await port.get(str(uuid4())) is None
        assert await port.get("not-an-id") is None
        assert await port.attach("not-an-id", {}) is None
