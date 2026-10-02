"""``portalab audit verify`` (T020): recompute the checkpoint chain and every covered batch.

A modified, inserted or removed entry inside a sealed range, or a broken link between checkpoints, fails
verification and emits ``audit.verification_failed``. Ranges whose entries were removed by partition
retention (older than the oldest retained ``seq``) are reported as ``pruned``, not as tampering.
"""

from dataclasses import dataclass, field

from sqlalchemy import func, select

from portalab.core.db import Database
from portalab.core.event_port import EventPublisher
from portalab.core.time import Clock, utc_now
from portalab.modules.authz.audit.checkpoints import GENESIS, batch_hash, chain_hash, entries_between
from portalab.modules.authz.models import AuditCheckpoint, AuditEntry
from portalab.modules.authz.observability import metrics


@dataclass
class VerificationReport:
    checked: int = 0
    pruned: int = 0
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


async def verify(
    database: Database,
    events: EventPublisher,
    *,
    from_seq: int | None = None,
    to_seq: int | None = None,
    clock: Clock | None = None,
) -> VerificationReport:
    report = VerificationReport()
    async with database.session() as session:
        checkpoints = list(
            (await session.execute(select(AuditCheckpoint).order_by(AuditCheckpoint.to_seq))).scalars()
        )
        oldest = await session.scalar(select(func.min(AuditEntry.seq)))
        prev = GENESIS
        for checkpoint in checkpoints:
            if checkpoint.prev_checkpoint_hash != prev:
                report.failures.append(f"checkpoint {checkpoint.id}: broken chain link")
            expected_chain = chain_hash(
                checkpoint.prev_checkpoint_hash,
                checkpoint.from_seq,
                checkpoint.to_seq,
                checkpoint.entry_count,
                checkpoint.batch_hash,
            )
            if expected_chain != checkpoint.checkpoint_hash:
                report.failures.append(f"checkpoint {checkpoint.id}: checkpoint hash mismatch")
            prev = checkpoint.checkpoint_hash
            in_window = (from_seq is None or checkpoint.to_seq >= from_seq) and (
                to_seq is None or checkpoint.from_seq <= to_seq
            )
            if not in_window:
                continue
            if oldest is None or checkpoint.from_seq < oldest:
                report.pruned += 1
                continue
            entries = await entries_between(session, checkpoint.from_seq, checkpoint.to_seq)
            if len(entries) != checkpoint.entry_count or batch_hash(entries) != checkpoint.batch_hash:
                report.failures.append(
                    f"checkpoint {checkpoint.id}: entries {checkpoint.from_seq}..{checkpoint.to_seq} changed"
                )
            report.checked += 1
    metrics.increment("authz.audit.verifications")
    if not report.ok:
        metrics.increment("authz.audit.verification_failed")
        async with database.unit_of_work() as uow:
            await events.publish(
                uow.session,
                "audit.verification_failed",
                {"failures": report.failures[:20]},
                occurred_at=utc_now(clock),
                source="audit",
            )
    return report
