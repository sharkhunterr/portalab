"""Bounded grants outside rules (T013/T014, T033; R9):

* ``grant_manual`` — an administrator (``rewards.grant``) grants a value with a mandatory reason; marked
  ``manual`` with the actor, audited (sensitive); amounts ≥ ``economy.manualGrantConfirmThreshold`` need a
  confirmation (handled by the API with the ConfirmationService). AI and automation callers are bounded by
  the acting principal's own permissions.
* ``grant_via_automation`` — 019 actions ``award.xp|coins|contribution``: author-bounded and subject to the
  anomaly guard like rule grants.
* ``grant_contribution`` — 016 conversions (``gamification.grant_contribution``): Contribution, once per
  source, subject to anti-abuse.
Level-ups and achievements unlocked by these grants are handled in the same transaction."""

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from portalab.capabilities.economy import Transaction, Value
from portalab.core.audit_port import AuditRecord, AuditSink
from portalab.core.authz_port import Authorizer, Principal, ResourceRef
from portalab.core.db import Database
from portalab.core.errors import Forbidden, ValidationFailed
from portalab.core.time import Clock, utc_now
from portalab.modules.gamification.achievements.evaluator import Achievements
from portalab.modules.gamification.anomaly.service import AnomalyService
from portalab.modules.gamification.antiabuse.guards import Guards
from portalab.modules.gamification.ledger.writer import Entry, LedgerWriter, lock_user
from portalab.modules.gamification.models import Balance, LedgerTransaction, Withheld
from portalab.modules.gamification.modifiers.rewards import RewardBonuses, boosted
from portalab.modules.gamification.notify import Note, Notifier
from portalab.modules.gamification.permissions import GRANT

MAX_GRANT = 1_000_000


class RewardServiceImpl:
    def __init__(
        self,
        database: Database,
        writer: LedgerWriter,
        guards: Guards,
        anomalies: AnomalyService,
        achievements: Achievements,
        notifier: Notifier,
        audit: AuditSink,
        authorizer: Authorizer,
        config: Any,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.writer = writer
        self.bonuses: RewardBonuses | None = None  # issue 226: set by the module
        self.guards = guards
        self.anomalies = anomalies
        self.achievements = achievements
        self.notifier = notifier
        self.audit = audit
        self.authorizer = authorizer
        self.config = config
        self.clock = clock

    async def _allowed(self, principal: Principal) -> None:
        if not await self.authorizer.is_allowed(principal, GRANT):
            raise Forbidden("You cannot grant rewards.", code="economy.grant_forbidden")

    @staticmethod
    def _check(value: str, amount: int) -> None:
        if value not in ("xp", "contribution", "coins"):
            raise ValidationFailed("Unknown value.", code="economy.invalid_value")
        if not 0 < amount <= MAX_GRANT:
            raise ValidationFailed("Grant a positive amount.", code="economy.invalid_amount")

    async def _grant(
        self,
        entry: Entry,
        *,
        guarded: bool,
        audit: Callable[[Any], Awaitable[None]] | None = None,
    ) -> Transaction | None:
        notes: list[Note] = []
        flags: list[UUID] = []
        result: Transaction | None = None
        async with self.database.unit_of_work() as uow:
            session = uow.session
            await lock_user(session, entry.user_id)
            anomaly = (
                await self.guards.anomaly(session, entry.user_id, entry.value, entry.delta, entry.occurred_at)
                if guarded
                else None
            )
            if anomaly is not None:
                flag, created = await self.anomalies.flag(session, entry.user_id, anomaly, entry.occurred_at)
                session.add(
                    Withheld(
                        user_id=entry.user_id,
                        value=entry.value,
                        proposed_delta=entry.delta,
                        reason="anomaly",
                        source_kind=entry.source_kind,
                        source_ref=entry.source_ref,
                        idempotency_key=entry.idempotency_key,
                        flag_id=flag.id,
                        status="flagged",
                        occurred_at=entry.occurred_at,
                    )
                )
                if created:
                    flags.append(flag.id)
            else:
                recorded = await self.writer.record(session, entry)
                result = recorded.transaction
                if not recorded.duplicate:
                    await self.guards.record(
                        session, entry.user_id, None, None, entry.value, entry.delta, entry.occurred_at
                    )
                    notes.append(
                        Note(
                            "reward",
                            entry.user_id,
                            f"reward:{entry.idempotency_key}",
                            {"value": entry.value, "amount": entry.delta},
                        )
                    )
                    if recorded.level_up:
                        notes.append(
                            Note(
                                "level_up",
                                entry.user_id,
                                f"level:{entry.user_id}:{recorded.level_up}",
                                {"level": recorded.level_up},
                            )
                        )
                    notes.extend(await self.achievements.evaluate(session, entry.user_id, entry.occurred_at))
            if audit is not None:
                await audit(session)
        for flag_id in flags:
            await self.anomalies.escalate(flag_id)
        await self.notifier.send(notes)
        return result

    async def grant_manual(
        self, actor: Principal, user: UUID, value: Value, amount: int, *, reason: str, idempotency_key: str
    ) -> Transaction | None:
        await self._allowed(actor)
        self._check(value, amount)
        reason = " ".join(reason.split())
        if len(reason) < 3:
            raise ValidationFailed("A reason is required.", code="economy.reason_required")
        now = utc_now(self.clock)
        admin = actor.acting_for or actor.user_id

        async def audit(session: Any) -> None:
            await self.audit.record(
                session,
                AuditRecord(
                    action="economy.manual_grant",
                    actor=actor,
                    resource=ResourceRef("progression", str(user), owner_id=user),
                    decision="allow",
                    context={"value": value, "amount": amount},
                    sensitive=True,
                ),
            )

        return await self._grant(
            Entry(
                user_id=user,
                value=value,
                delta=amount,
                kind="manual",
                source_kind="manual",
                source_ref=f"admin:{admin}",
                idempotency_key=f"manual:{idempotency_key}",
                occurred_at=now,
                base_amount=amount,
                actor_user_id=admin,
                reason=reason,
            ),
            guarded=False,
            audit=audit,
        )

    async def withdraw_manual(
        self, actor: Principal, user: UUID, value: Value, amount: int, *, reason: str, idempotency_key: str
    ) -> Transaction:
        """#98: an administrator takes a value back (Coins, XP, Contribution) — never below zero, with a
        reason; a correction in the ledger, audited."""
        await self._allowed(actor)
        self._check(value, amount)
        reason = " ".join(reason.split())
        if len(reason) < 3:
            raise ValidationFailed("A reason is required.", code="economy.reason_required")
        now = utc_now(self.clock)
        admin = actor.acting_for or actor.user_id
        async with self.database.unit_of_work() as uow:
            session = uow.session
            await lock_user(session, user)
            balance = await session.get(Balance, (user, value))
            take = min(amount, balance.amount if balance is not None else 0)
            if take <= 0:
                raise ValidationFailed("There is nothing to take back.", code="economy.nothing_to_take")
            recorded = await self.writer.record(
                session,
                Entry(
                    user_id=user,
                    value=value,
                    delta=-take,
                    kind="correction",
                    source_kind="manual",
                    source_ref=f"admin:{admin}",
                    idempotency_key=f"withdraw:{idempotency_key}",
                    occurred_at=now,
                    actor_user_id=admin,
                    reason=reason,
                ),
            )
            await self.audit.record(
                session,
                AuditRecord(
                    action="economy.manual_withdrawal",
                    actor=actor,
                    resource=ResourceRef("progression", str(user), owner_id=user),
                    decision="allow",
                    context={"value": value, "amount": take},
                    sensitive=True,
                ),
            )
        return recorded.transaction

    async def reverse(self, actor: Principal, transaction_id: UUID, *, reason: str) -> Transaction:
        """#98: an entry of a member's history cancelled — what it gave taken back (as far as the balance
        allows), what it took given back; the ledger keeps both, the correction pointing at the entry."""
        await self._allowed(actor)
        reason = " ".join(reason.split())
        if len(reason) < 3:
            raise ValidationFailed("A reason is required.", code="economy.reason_required")
        now = utc_now(self.clock)
        admin = actor.acting_for or actor.user_id
        async with self.database.unit_of_work() as uow:
            session = uow.session
            original = await session.get(LedgerTransaction, transaction_id)
            if original is None:
                raise ValidationFailed("This entry does not exist.", code="economy.unknown_transaction")
            await lock_user(session, original.user_id)
            undone = int(
                await session.scalar(
                    select(func.coalesce(func.sum(LedgerTransaction.delta), 0)).where(
                        LedgerTransaction.reverses_transaction_id == transaction_id
                    )
                )
                or 0
            )
            remaining = original.delta + undone
            if remaining > 0:
                balance = await session.get(Balance, (original.user_id, original.value))
                remaining = min(remaining, balance.amount if balance is not None else 0)
            if remaining == 0:
                raise ValidationFailed("This entry was already cancelled.", code="economy.already_reversed")
            count = int(
                await session.scalar(
                    select(func.count()).where(LedgerTransaction.reverses_transaction_id == transaction_id)
                )
                or 0
            )
            recorded = await self.writer.record(
                session,
                Entry(
                    user_id=original.user_id,
                    value=original.value,
                    delta=-remaining,
                    kind="correction",
                    source_kind="manual",
                    source_ref=f"admin:{admin}",
                    idempotency_key=f"reverse:{transaction_id}:{count}",
                    occurred_at=now,
                    actor_user_id=admin,
                    reason=reason,
                    reverses_transaction_id=transaction_id,
                ),
            )
            await self.audit.record(
                session,
                AuditRecord(
                    action="economy.entry_reversed",
                    actor=actor,
                    resource=ResourceRef("progression", str(original.user_id), owner_id=original.user_id),
                    decision="allow",
                    context={"transaction": str(transaction_id), "delta": -remaining},
                    sensitive=True,
                ),
            )
        return recorded.transaction

    async def grant_via_automation(
        self,
        principal: Principal,
        user: UUID,
        value: Value,
        amount: int,
        *,
        automation_ref: str,
        idempotency_key: str,
    ) -> Transaction | None:
        await self._allowed(principal)  # the automation's author must hold rewards.grant
        self._check(value, amount)
        return await self._grant(
            Entry(
                user_id=user,
                value=value,
                kind="grant",
                source_kind="automation",
                source_ref=automation_ref[:200],
                idempotency_key=f"automation:{idempotency_key}",
                occurred_at=utc_now(self.clock),
                base_amount=amount,
                # issue 226: the streak, the campaigns, a boost — like an action's gains
                **await boosted(self.bonuses, user, "automation", value, amount, utc_now(self.clock)),
                actor_user_id=principal.acting_for or principal.user_id,
            ),
            guarded=True,
        )

    async def grant_contribution(self, user: UUID, kind: str, source_ref: str, actor: Principal) -> str:
        """016 ``ContributionGrant``: once per source; anti-abuse applies."""
        amount = max(1, int(self.config().contribution_amount))
        transaction = await self._grant(
            Entry(
                user_id=user,
                value="contribution",
                kind="grant",
                source_kind="contribution",
                source_ref=f"{kind}:{source_ref}"[:200],
                idempotency_key=f"contribution:{source_ref}",
                occurred_at=utc_now(self.clock),
                base_amount=amount,
                # issue 226: the streak, the campaigns, a boost — like an action's gains
                **await boosted(
                    self.bonuses, user, "contribution", "contribution", amount, utc_now(self.clock)
                ),
                actor_user_id=actor.acting_for or actor.user_id,
            ),
            guarded=True,
        )
        return str(transaction.id) if transaction else "withheld"

    async def unlock(self, principal: Principal, user: UUID, achievement: str) -> bool:
        """019 ``reward.unlock``: unlock an achievement for a user (author-bounded)."""
        await self._allowed(principal)
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            await lock_user(uow.session, user)
            notes = await self.achievements.unlock_by_key(uow.session, user, achievement, now)
        await self.notifier.send(notes)
        return bool(notes)
