"""Privacy participant (T003): a user's personal statistic buckets/members, unlocks and Wrapped snapshots
are exported and erased with the account; community aggregates (contributors only as salted hashes) stay."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, select

from portalab.capabilities.privacy_participants import ErasureMode, ExportRecord
from portalab.core.db import Database
from portalab.modules.statistics.models import Bucket, Member, Unlock, WrappedSnapshot


class StatisticsParticipant:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def export(self, user_id: UUID) -> Sequence[ExportRecord]:
        async with self.database.session() as session:
            personal = (
                await session.execute(
                    select(
                        Bucket.stat_key,
                        func.sum(Bucket.count),
                        func.min(Bucket.bucket_day),
                        func.max(Bucket.bucket_day),
                    )
                    .where(Bucket.scope_type == "personal", Bucket.scope_id == user_id)
                    .group_by(Bucket.stat_key)
                )
            ).all()
            unlocks = (await session.execute(select(Unlock).where(Unlock.user_id == user_id))).scalars().all()
            snapshots = (
                (await session.execute(select(WrappedSnapshot).where(WrappedSnapshot.user_id == user_id)))
                .scalars()
                .all()
            )
        records = [
            ExportRecord(
                "statistics.personal",
                {"statistic": key, "events": int(count), "from": str(first), "to": str(last)},
            )
            for key, count, first, last in personal
        ]
        records += [
            ExportRecord("statistics.unlock", {"statistic": u.stat_key, "at": u.unlocked_at.isoformat()})
            for u in unlocks
        ]
        records += [
            ExportRecord(
                "statistics.wrapped",
                {"recap": s.wrapped_key, "period_start": str(s.period_start), "payload": s.payload},
            )
            for s in snapshots
        ]
        return records

    async def erase(self, user_id: UUID, mode: ErasureMode) -> None:
        async with self.database.unit_of_work() as uow:
            for model in (Bucket, Member):
                await uow.session.execute(
                    delete(model).where(model.scope_type == "personal", model.scope_id == user_id)
                )
            await uow.session.execute(delete(Unlock).where(Unlock.user_id == user_id))
            await uow.session.execute(delete(WrappedSnapshot).where(WrappedSnapshot.user_id == user_id))
