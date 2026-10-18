"""030 T056 (FR-026, issue 144) — the audit trail copied off the machine: every entry, in order and once, to
a JSON-lines file and to a syslog server (RFC 5424, octet-counted); the copy resumes where it stopped."""

import asyncio
import json
from pathlib import Path

from sqlalchemy import func, select

from portalab.core.audit_port import AuditRecord
from portalab.core.authz_port import Principal, ResourceRef
from portalab.modules.authz.audit.offsite import AuditCopier
from portalab.modules.authz.models import AuditEntry
from tests.events_fixtures import EventsHarness


async def test_entries_are_copied_once_in_order(ev: EventsHarness, tmp_path: Path) -> None:
    database = ev.full.database
    for action in ("test.first", "test.second"):
        async with database.unit_of_work() as uow:
            await ev.full.authz.audit.record(
                uow.session,
                AuditRecord(
                    action=action,
                    actor=Principal(channel="system"),
                    resource=ResourceRef("test", "1"),
                    decision="allow",
                ),
            )
    async with database.session() as session:
        total = int(await session.scalar(select(func.count()).select_from(AuditEntry)) or 0)
    received: list[bytes] = []

    async def server(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        received.append(await reader.read())
        writer.close()

    listening = await asyncio.start_server(server, "127.0.0.1", 0)
    port = listening.sockets[0].getsockname()[1]
    copier = AuditCopier(database, tmp_path)
    sink = tmp_path / "audit.jsonl"
    copied = 0
    while (step := await copier.run_once(file=str(sink), syslog=f"127.0.0.1:{port}")) > 0:
        copied += step
    await asyncio.sleep(0.2)
    listening.close()
    lines = [json.loads(line) for line in sink.read_text().splitlines()]
    assert copied == total == len(lines)
    seqs = [line["seq"] for line in lines]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    assert total >= 2
    if total:
        frames = b"".join(received)
        assert frames.count(b"portalab - audit -") == total and b"<133>1 " in frames
    assert await copier.run_once(file=str(sink)) == 0  # nothing new: nothing copied again
