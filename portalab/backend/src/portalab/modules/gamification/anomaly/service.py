"""Anomaly review (T021/T022; R7): a burst beyond the thresholds withholds the grant and opens a flag
(``economy.anomaly_flagged``); an administrator (``economy.manage``) approves (the withheld grants are
recorded), rejects (dropped with a reason) or confirms abuse (withheld rejected **and** the window's rule
grants reversed by correction transactions — never edits). Every decision is audited; nothing is dropped
silently. Optional escalation to an incident (016) with ``economy.anomaly.escalateToIncident``."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.health import INCIDENTS
from portalab.capabilities.registry import CapabilityRegistry
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Conflict, NotFound
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.gamification.antiabuse.windows import window_start
from portalab.modules.gamification.ledger.writer import Entry, LedgerWriter, lock_user
from portalab.modules.gamification.models import AnomalyFlag, Balance, LedgerTransaction, Withheld
from portalab.modules.gamification.observability import log, metrics

WINDOW = {"grants_per_hour": "hour", "coins_per_day": "day"}


class FlagNotFound(NotFound):
    default_code = "economy.anomaly_not_found"
    default_title = "Anomaly not found"


class AnomalyService:
    def __init__(
        self,
        database: Database,
        writer: LedgerWriter,
        events: EventPublisher,
        audit: AuditSink,
        capabilities: CapabilityRegistry,
        config: Any,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.writer = writer
        self.events = events
        self.audit = audit
        self.capabilities = capabilities
        self.config = config
        self.clock = clock

    async def flag(
        self, session: AsyncSession, user: UUID, kind: str, at: datetime
    ) -> tuple[AnomalyFlag, bool]:
        start = window_start(WINDOW.get(kind, "day"), at, self.config().timezone)
        existing = (
            await session.execute(
                select(AnomalyFlag).where(
                    AnomalyFlag.user_id == user,
                    AnomalyFlag.kind == kind,
                    AnomalyFlag.window_start == start,
                    AnomalyFlag.status == "open",
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing, False
        config = self.config()
        threshold = (
            config.anomaly_max_grants_per_hour
            if kind == "grants_per_hour"
            else config.anomaly_max_coins_per_day
        )
        flag = AnomalyFlag(
            user_id=user,
            kind=kind,
            window_start=start,
            evidence={"threshold": threshold},
            status="open",
            created_at=utc_now(self.clock),
        )
        session.add(flag)
        await session.flush()
        await self.events.publish(
            session,
            "economy.anomaly_flagged",
            {"kind": kind},
            occurred_at=at,
            actor=Principal(channel="system"),
            subject=SubjectRef("user", str(user)),
            dedup_key=f"economy.anomaly_flagged:{flag.id}",
        )
        metrics.increment("gamification.anomalies.flagged")
        return flag, True

    async def escalate(self, flag_id: UUID) -> None:
        if not self.config().anomaly_escalate_to_incident:
            return
        try:
            providers = self.capabilities.system_providers(INCIDENTS)
            if providers:
                await providers[0].provider.create(
                    title="Economy anomaly flagged",
                    source="economy",
                    severity="minor",
                    evidence={"anomaly": str(flag_id)},
                    dedup_key=f"economy:{flag_id}",
                )
        except Exception:
            log.warning("economy anomaly not escalated")

    async def queue(self, status: str = "open") -> list[tuple[AnomalyFlag, list[Withheld]]]:
        async with self.database.session() as session:
            flags = list(
                (
                    await session.execute(
                        select(AnomalyFlag)
                        .where(AnomalyFlag.status == status)
                        .order_by(AnomalyFlag.created_at)
                    )
                ).scalars()
            )
            withheld = list(
                (
                    await session.execute(select(Withheld).where(Withheld.flag_id.in_([f.id for f in flags])))
                ).scalars()
            )
        return [(f, [w for w in withheld if w.flag_id == f.id]) for f in flags]

    async def _load(self, session: AsyncSession, flag_id: UUID) -> AnomalyFlag:
        flag = await session.get(AnomalyFlag, flag_id, with_for_update=True)
        if flag is None:
            raise FlagNotFound("This anomaly does not exist.")
        if flag.status != "open":
            raise Conflict("This anomaly was already reviewed.", code="economy.anomaly_reviewed")
        await lock_user(session, flag.user_id)
        return flag

    async def _pending(self, session: AsyncSession, flag: AnomalyFlag) -> list[Withheld]:
        return list(
            (
                await session.execute(
                    select(Withheld)
                    .where(Withheld.flag_id == flag.id, Withheld.status == "flagged")
                    .with_for_update()
                )
            ).scalars()
        )

    async def _audit(
        self, session: AsyncSession, actor: Principal, action: str, flag: AnomalyFlag, **context: Any
    ) -> None:
        await self.audit.record(
            session,
            AuditRecord(
                action=action,
                actor=actor,
                resource=ResourceRef("economy_anomaly", str(flag.id), owner_id=flag.user_id),
                decision="allow",
                context=context,
                sensitive=True,
            ),
        )

    async def approve(self, actor: Principal, flag_id: UUID, reason: str) -> list[UUID]:
        now = utc_now(self.clock)
        created: list[UUID] = []
        async with self.database.unit_of_work() as uow:
            flag = await self._load(uow.session, flag_id)
            for item in await self._pending(uow.session, flag):
                recorded = await self.writer.record(
                    uow.session,
                    Entry(
                        user_id=item.user_id,
                        value=item.value,
                        delta=item.proposed_delta,
                        kind="grant",
                        source_kind=item.source_kind,
                        source_ref=item.source_ref,
                        rule_key=item.rule_key,
                        rule_version=item.rule_version,
                        trigger_event_id=item.trigger_event_id,
                        idempotency_key=item.idempotency_key,
                        occurred_at=item.occurred_at,
                        guards={"anomaly": flag.kind, "approved": True},
                        actor_user_id=actor.acting_for or actor.user_id,
                    ),
                )
                created.append(recorded.transaction.id)
                item.status, item.reviewed_by, item.reviewed_at, item.decision_reason = (
                    "approved",
                    actor.acting_for or actor.user_id,
                    now,
                    reason[:200],
                )
            flag.status, flag.reviewed_by, flag.reviewed_at = (
                "dismissed",
                actor.acting_for or actor.user_id,
                now,
            )
            await self._audit(uow.session, actor, "economy.anomaly_approved", flag, granted=len(created))
        return created

    async def reject(self, actor: Principal, flag_id: UUID, reason: str) -> int:
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            flag = await self._load(uow.session, flag_id)
            pending = await self._pending(uow.session, flag)
            for item in pending:
                item.status, item.reviewed_by, item.reviewed_at, item.decision_reason = (
                    "rejected",
                    actor.acting_for or actor.user_id,
                    now,
                    reason[:200],
                )
            flag.status, flag.reviewed_by, flag.reviewed_at = (
                "dismissed",
                actor.acting_for or actor.user_id,
                now,
            )
            await self._audit(uow.session, actor, "economy.anomaly_rejected", flag, dropped=len(pending))
        return len(pending)

    async def confirm_abuse(self, actor: Principal, flag_id: UUID, reason: str) -> list[UUID]:
        """Withheld grants rejected; the flagged window's rule grants reversed by correction transactions."""
        now = utc_now(self.clock)
        corrections: list[UUID] = []
        async with self.database.unit_of_work() as uow:
            session = uow.session
            flag = await self._load(session, flag_id)
            for item in await self._pending(session, flag):
                item.status, item.reviewed_by, item.reviewed_at, item.decision_reason = (
                    "rejected",
                    actor.acting_for or actor.user_id,
                    now,
                    reason[:200],
                )
            span = {"hour": 3600, "day": 86400}[WINDOW.get(flag.kind, "day")]
            end = flag.window_start + timedelta(seconds=span)
            grants = list(
                (
                    await session.execute(
                        select(LedgerTransaction)
                        .where(
                            LedgerTransaction.user_id == flag.user_id,
                            LedgerTransaction.kind == "grant",
                            LedgerTransaction.source_kind == "reward_rule",
                            LedgerTransaction.occurred_at >= flag.window_start,
                            LedgerTransaction.occurred_at < end,
                        )
                        .order_by(LedgerTransaction.seq)
                    )
                ).scalars()
            )
            for grant in grants:
                balance = await session.get(Balance, (grant.user_id, grant.value))
                amount = min(grant.delta, balance.amount if balance else 0)
                if amount <= 0:
                    continue
                recorded = await self.writer.record(
                    session,
                    Entry(
                        user_id=grant.user_id,
                        value=grant.value,
                        delta=-amount,
                        kind="correction",
                        source_kind="system",
                        source_ref=f"anomaly:{flag.id}",
                        idempotency_key=f"correction:{grant.id}",
                        occurred_at=now,
                        actor_user_id=actor.acting_for or actor.user_id,
                        reason=reason,
                        reverses_transaction_id=grant.id,
                    ),
                )
                corrections.append(recorded.transaction.id)
            flag.status, flag.reviewed_by, flag.reviewed_at = (
                "confirmed",
                actor.acting_for or actor.user_id,
                now,
            )
            await self._audit(session, actor, "economy.anomaly_confirmed", flag, corrections=len(corrections))
        return corrections
