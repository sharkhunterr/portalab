"""``RequestQuotaService`` (T026; R12, OQ-72, CD-034): Media owns request quotas — a base allowance per
period (``media.requests.quotaPerPeriod`` / ``.period``) plus **extra units** credited by Marketplace (015)
through ``add_units`` (idempotent, ledgered). Units only allow *more* requests: queue order and priority
never depend on them."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.db import Database
from portalab.core.errors import PortalError, ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.media.models import MediaRequest, QuotaLedger, QuotaUnits


class QuotaExceeded(PortalError):
    status = 429
    default_code = "media.request_quota_exceeded"
    default_title = "Request quota reached"


def period_start(now: datetime, period: str) -> datetime:
    day = datetime(now.year, now.month, now.day, tzinfo=UTC)
    if period == "day":
        return day
    if period == "month":
        return day.replace(day=1)
    return day - timedelta(days=day.weekday())  # week (Monday)


class RequestQuota:
    def __init__(self, database: Database, config: Any, *, clock: Clock | None = None) -> None:
        self.database = database
        self.config = config  # callable → MediaConfig
        self.clock = clock

    async def _usage(self, session: AsyncSession, user: UUID) -> tuple[int, int, datetime]:
        config = self.config()
        start = period_start(utc_now(self.clock), config.quota_period)
        used = await session.scalar(
            select(func.count()).where(
                MediaRequest.requester_user_id == user,
                MediaRequest.counted == "base",
                MediaRequest.requested_at >= start,
            )
        )
        units = await session.get(QuotaUnits, user)
        return int(used or 0), int(units.units_remaining) if units else 0, start

    async def available(self, user: UUID) -> dict[str, int]:
        async with self.database.session() as session:
            used, extra, _ = await self._usage(session, user)
        limit = max(0, self.config().quota_per_period)
        return {
            "base_limit": limit,
            "base_used": used,
            "base_remaining": max(0, limit - used),
            "extra_units": extra,
        }

    async def summary(self, user: UUID) -> dict[str, Any]:
        async with self.database.session() as session:
            used, extra, start = await self._usage(session, user)
        limit = max(0, self.config().quota_per_period)
        return {
            "base_limit": limit,
            "base_used": used,
            "base_remaining": max(0, limit - used),
            "extra_units": extra,
            "period": self.config().quota_period,
            "period_start": start.isoformat(),
        }

    async def consume(self, session: AsyncSession, user: UUID, request_ref: str) -> str:
        """Count one request against the base allowance, else one extra unit; raises when none is left."""
        used, extra, _ = await self._usage(session, user)
        if used < max(0, self.config().quota_per_period):
            return "base"
        if extra > 0:
            await self._ledger(session, user, -1, "consumption", request_ref, f"consume:{request_ref}")
            return "extra"
        raise QuotaExceeded("You have used your requests for this period.")

    async def give_back(self, session: AsyncSession, user: UUID, request_ref: str, counted: str) -> None:
        if counted == "extra":
            await self._ledger(session, user, 1, "refund", request_ref, f"giveback:{request_ref}")

    async def _ledger(
        self, session: AsyncSession, user: UUID, delta: int, reason: str, source_ref: str, key: str
    ) -> bool:
        now = utc_now(self.clock)
        inserted = (
            await session.execute(
                insert(QuotaLedger)
                .values(
                    user_id=user,
                    delta=delta,
                    reason=reason,
                    source_ref=source_ref[:200],
                    idempotency_key=key[:200],
                    created_at=now,
                )
                .on_conflict_do_nothing(constraint="uq_request_quota_ledger_idempotency")
                .returning(QuotaLedger.id)
            )
        ).scalar_one_or_none()
        if inserted is None:
            return False
        row = await session.get(QuotaUnits, user, with_for_update=True)
        if row is None:
            session.add(QuotaUnits(user_id=user, units_remaining=max(0, delta), updated_at=now))
        else:
            row.units_remaining, row.updated_at = max(0, row.units_remaining + delta), now
        return True

    async def add_units(self, user: UUID, units: int, source_ref: str, idempotency_key: str) -> int:
        if units <= 0:
            raise ValidationFailed("Units must be positive.", code="media.invalid")
        async with self.database.unit_of_work() as uow:
            await self._ledger(uow.session, user, units, "purchase", source_ref, idempotency_key)
            row = await uow.session.get(QuotaUnits, user)
            return int(row.units_remaining) if row else 0

    async def remove_units(self, user: UUID, units: int, source_ref: str, idempotency_key: str) -> int:
        if units <= 0:
            raise ValidationFailed("Units must be positive.", code="media.invalid")
        async with self.database.unit_of_work() as uow:
            await self._ledger(uow.session, user, -units, "refund", source_ref, idempotency_key)
            row = await uow.session.get(QuotaUnits, user)
            return int(row.units_remaining) if row else 0
