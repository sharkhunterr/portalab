"""Reward consumer (T016; R4, R8): turns domain events into ledger grants, deterministically.

For an event, inside **one transaction** serialized per user (advisory lock):
* the event is marked applied — a redelivery is a no-op (counters and grants happen once);
* every rule version **in force at ``occurred_at``** whose closed predicate matches computes its base
  amounts, applies the multiplicative modifiers (capped), then the anti-abuse guards (cooldown,
  diminishing returns, caps, anomaly) — withheld grants are recorded, never silently dropped;
* grants are written by the ``LedgerWriter`` (idempotency ``rule:<event>:<rule>:<value>``), then
  achievement counters advance and unlocked achievements are granted once.
Notifications are sent after commit; a notification failure never affects the reward."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.capabilities.events import Consumer, ConsumerContext, Envelope
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.gamification.achievements.evaluator import Achievements
from portalab.modules.gamification.anomaly.service import AnomalyService
from portalab.modules.gamification.antiabuse.guards import Guards
from portalab.modules.gamification.calculator.calculator import base_amounts
from portalab.modules.gamification.events import OWN_TYPES
from portalab.modules.gamification.ledger.writer import Entry, LedgerWriter, lock_user
from portalab.modules.gamification.models import AppliedEvent, PlayKind, Withheld
from portalab.modules.gamification.modifiers.combiner import ModifierCombiner
from portalab.modules.gamification.notify import Note, Notifier
from portalab.modules.gamification.observability import metrics
from portalab.modules.gamification.rules.definition import matches
from portalab.modules.gamification.rules.store import RuleStore, RuleVersion

CONSUMER = "gamification.rewards"
OWNER = "module:gamification"


# issue 160: the sittings whose kind the progression shows (a play finished or interrupted)
SITTINGS = frozenset({"media.playback_finished", "media.playback_abandoned"})


def _seconds(raw: Any) -> int:
    try:
        return max(0, min(86_400, int(float(raw))))
    except (TypeError, ValueError):
        return 0


@dataclass
class Outcome:
    notes: list[Note] = field(default_factory=list)
    flags: list[UUID] = field(default_factory=list)
    granted: int = 0
    withheld: int = 0


def recipient(envelope: Envelope) -> UUID | None:
    if envelope.actor_user_id is not None:
        return envelope.actor_user_id
    if envelope.subject_type == "user" and envelope.subject_id:
        try:
            return UUID(envelope.subject_id)
        except ValueError:
            return None
    return None


class RewardPipeline:
    def __init__(
        self,
        database: Database,
        writer: LedgerWriter,
        rules: RuleStore,
        combiner: ModifierCombiner,
        guards: Guards,
        anomalies: AnomalyService,
        achievements: Achievements,
        notifier: Notifier,
        config: Any,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.writer = writer
        self.rules = rules
        self.combiner = combiner
        self.guards = guards
        self.anomalies = anomalies
        self.achievements = achievements
        self.notifier = notifier
        self.quests: Any = None  # slice C: set by the module (``Quests``)
        self.config = config
        self.clock = clock

    def consumer(self) -> Consumer:
        return Consumer(CONSUMER, frozenset({"*"}), self.handle, OWNER)

    async def handle(self, envelope: Envelope, ctx: ConsumerContext) -> None:
        await self.process(envelope)

    async def process(self, envelope: Envelope) -> Outcome:
        outcome = Outcome()
        # the engine's own events (a quest completed, an achievement unlocked…) never feed a rule — a grant
        # would come back as an event — but achievements and quests may count them (#108: « complete five
        # quests », « drop by on three days »); each completes once a period, so the chain ends
        own = envelope.type in OWN_TYPES
        rules = [] if own else await self.rules.in_force(envelope.type, envelope.occurred_at)
        if (
            not rules
            and not await self.achievements.tracks(envelope.type, envelope.occurred_at)
            and not (self.quests and await self.quests.tracks(envelope.type, envelope.occurred_at))
        ):
            return outcome
        user = recipient(envelope)
        if user is None:
            return outcome
        async with self.database.unit_of_work() as uow:
            session = uow.session
            await lock_user(session, user)
            first = (
                await session.execute(
                    insert(AppliedEvent)
                    .values(event_id=envelope.event_id, user_id=user, applied_at=utc_now(self.clock))
                    .on_conflict_do_nothing()
                    .returning(AppliedEvent.event_id)
                )
            ).scalar_one_or_none()
            if first is None:
                metrics.increment("gamification.events.duplicate")
                return outcome
            kind = envelope.payload.get("kind")
            if envelope.type in SITTINGS and isinstance(kind, str) and kind:
                # issue 160: the play's kind, so its gains show by kind (episode, film, book…)
                await session.execute(
                    insert(PlayKind)
                    .values(
                        event_id=envelope.event_id,
                        user_id=user,
                        kind=kind[:24],
                        object=str(envelope.payload.get("object") or "")[:64] or None,
                        finished=envelope.type == "media.playback_finished",
                        watched_s=_seconds(envelope.payload.get("watched_s")),
                        occurred_at=envelope.occurred_at,
                    )
                    .on_conflict_do_nothing()
                )
            for rule in rules:
                if matches(rule.definition.predicate, envelope.payload):
                    await self._apply(session, user, rule, envelope, outcome)
            outcome.notes.extend(await self.achievements.on_event(session, user, envelope))
            if self.quests is not None:
                outcome.notes.extend(await self.quests.on_event(session, user, envelope))
        for flag in outcome.flags:
            await self.anomalies.escalate(flag)
        await self.notifier.send(outcome.notes)
        return outcome

    async def _apply(
        self, session: AsyncSession, user: UUID, rule: RuleVersion, envelope: Envelope, outcome: Outcome
    ) -> None:
        config = self.config()
        at = envelope.occurred_at
        for value, base in base_amounts(rule.definition, envelope.payload):
            key = f"rule:{envelope.event_id}:{rule.key}:{value}"
            combined = await self.combiner.combined(
                user,
                envelope,
                value,  # type: ignore[arg-type]
                at,
                rule.definition.multiplier,
                config.max_total_boost,
            )
            amount = combined.apply(base)
            verdict = await self.guards.rule_guards(
                session, user, rule.key, rule.definition.limits, value, amount, at
            )
            common: dict[str, Any] = {
                "user_id": user,
                "value": value,
                "source_kind": "reward_rule",
                "source_ref": f"event:{envelope.event_id}",
                "rule_key": rule.key,
                "rule_version": rule.version,
                "trigger_event_id": envelope.event_id,
                "idempotency_key": key,
                "occurred_at": at,
            }
            if verdict.withheld is not None:
                await self._withhold(session, common, amount, verdict.withheld, "dropped", None)
                outcome.withheld += 1
                continue
            anomaly = await self.guards.anomaly(session, user, value, verdict.amount, at)
            if anomaly is not None:
                flag, created = await self.anomalies.flag(session, user, anomaly, at)
                await self._withhold(session, common, verdict.amount, "anomaly", "flagged", flag.id)
                if created:
                    outcome.flags.append(flag.id)
                outcome.withheld += 1
                continue
            recorded = await self.writer.record(
                session,
                Entry(
                    delta=verdict.amount,
                    kind="grant",
                    base_amount=base,
                    multiplier=round(combined.factor, 4),
                    modifiers=combined.record(),
                    guards=verdict.effects,
                    **common,
                ),
            )
            if recorded.duplicate:
                continue
            await self.guards.record(
                session, user, rule.key, rule.definition.limits, value, verdict.amount, at
            )
            outcome.granted += 1
            metrics.increment(f"gamification.grants.{value}")
            outcome.notes.append(
                Note(
                    "reward",
                    user,
                    f"reward:{key}",
                    {
                        "value": value,
                        "amount": verdict.amount,
                        "rule": rule.key,
                        # #55: a boost bought in the shop shows on each gain it multiplied
                        "boost": next(
                            (
                                f"{float(m['factor']):g}"
                                for m in combined.applied
                                if str(m.get("source_ref", "")).startswith("boost:")
                            ),
                            "none",
                        ),
                    },
                )
            )
            if recorded.level_up:
                outcome.notes.append(
                    Note("level_up", user, f"level:{user}:{recorded.level_up}", {"level": recorded.level_up})
                )

    async def _withhold(
        self,
        session: AsyncSession,
        common: dict[str, Any],
        amount: int,
        reason: str,
        status: str,
        flag: UUID | None,
    ) -> None:
        if amount <= 0 and reason == "anomaly":
            return
        session.add(
            Withheld(
                user_id=common["user_id"],
                value=common["value"],
                proposed_delta=max(0, amount),
                reason=reason,
                source_kind=common["source_kind"],
                source_ref=common["source_ref"],
                rule_key=common["rule_key"],
                rule_version=common["rule_version"],
                trigger_event_id=common["trigger_event_id"],
                idempotency_key=common["idempotency_key"],
                flag_id=flag,
                status=status,
                occurred_at=common["occurred_at"],
            )
        )
        metrics.increment(f"gamification.withheld.{reason}")
