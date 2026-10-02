"""021 T016 — checkpoints chain correctly, verification passes; altering or removing a sealed row
(superuser in tests) fails verification and emits ``audit.verification_failed``."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text

from portalab.core.audit_port import AuditRecord
from portalab.core.event_port import OutboxEvent
from portalab.modules.authz.audit.checkpoints import create_checkpoint
from portalab.modules.authz.audit.verify import verify
from tests.privacy_fixtures import FullPlatform


async def _write(full: FullPlatform, count: int) -> None:
    for index in range(count):
        await full.authz.audit.record(
            None, AuditRecord(action=f"test.{index}", actor=None, context={"n": index})
        )


async def _seal(full: FullPlatform) -> object:
    later = datetime.now(UTC) + timedelta(hours=1)  # past the settle delay
    return await create_checkpoint(full.database, full.authz.events, now=later)


async def test_chain_and_verification(full: FullPlatform) -> None:
    await _write(full, 5)
    first = await _seal(full)
    assert first is not None and first.count == 5  # type: ignore[attr-defined]
    assert await _seal(full) is None  # nothing new to seal
    await _write(full, 3)
    second = await _seal(full)
    assert second.from_seq == first.to_seq + 1  # type: ignore[attr-defined]
    report = await verify(full.database, full.authz.events)
    assert report.ok and report.checked == 2


async def test_tampering_is_detected(full: FullPlatform) -> None:
    await _write(full, 4)
    await _seal(full)
    async with full.database.engine.begin() as conn:  # superuser bypass, test only
        await conn.execute(text("ALTER TABLE audit.audit_entries DISABLE TRIGGER USER"))
        await conn.execute(text("UPDATE audit.audit_entries SET action = 'forged' WHERE action = 'test.2'"))
        await conn.execute(text("ALTER TABLE audit.audit_entries ENABLE TRIGGER USER"))
    report = await verify(full.database, full.authz.events)
    assert not report.ok and "changed" in report.failures[0]
    async with full.database.session() as session:
        assert (
            "audit.verification_failed" in (await session.execute(select(OutboxEvent.type))).scalars().all()
        )


async def test_removed_row_is_detected(full: FullPlatform) -> None:
    await _write(full, 3)
    await _seal(full)
    async with full.database.engine.begin() as conn:
        await conn.execute(text("ALTER TABLE audit.audit_entries DISABLE TRIGGER USER"))
        await conn.execute(text("DELETE FROM audit.audit_entries WHERE action = 'test.1'"))
        await conn.execute(text("ALTER TABLE audit.audit_entries ENABLE TRIGGER USER"))
    assert not (await verify(full.database, full.authz.events)).ok
