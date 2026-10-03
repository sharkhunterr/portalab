"""Event triggers (T009, T021): one 007 consumer (``replay_safe=False`` — replays never re-run automations)
sees every event; active automations whose trigger matches (type + field filter on declared attributes)
are admitted by the Gate and run. ``relative`` triggers schedule a pending fire at the event's reference
time plus the offset. Payload bodies are only used in memory (substitution), never stored."""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from portalab.capabilities.events import Consumer, ConsumerContext, Envelope, EventTypeRegistry
from portalab.core.db import Database
from portalab.core.time import Clock, utc_now
from portalab.modules.automations.definitions.schema import Definition
from portalab.modules.automations.definitions.validate import event_fields
from portalab.modules.automations.gate.gate import Gate, TriggerInfo
from portalab.modules.automations.models import Automation, AutomationVersion, PendingFire
from portalab.modules.automations.observability import log
from portalab.modules.automations.registries.conditions import compare
from portalab.modules.automations.runner.runner import Runner

CONSUMER = "automations.triggers"
OWNER = "module:automations"
CACHE_SECONDS = 5.0


@dataclass(frozen=True, slots=True)
class Live:
    id: UUID
    key: str
    version: int
    definition: Definition


def scope_of(envelope: Envelope | None, automation_key: str, fields: set[str]) -> dict[str, Any]:
    scope: dict[str, Any] = {"automation.key": automation_key}
    if envelope is None:
        return scope
    scope |= {
        "event.id": str(envelope.event_id),
        "event.occurred_at": envelope.occurred_at.isoformat(),
        "subject.id": envelope.subject_id,
        "subject.type": envelope.subject_type,
        "actor.id": str(envelope.actor_user_id) if envelope.actor_user_id else None,
    }
    for field_name in fields:
        if field_name in envelope.payload:
            scope[f"event.{field_name}"] = envelope.payload[field_name]
    return scope


def lineage(envelope: Envelope | None) -> list[str]:
    """Ancestor automations of an event (set by the runner's provenance scope)."""
    if envelope is None:
        return []
    automation = envelope.provenance.get("automation") if isinstance(envelope.provenance, dict) else None
    path = automation.get("path") if isinstance(automation, dict) else None
    return [str(p) for p in path][:20] if isinstance(path, list) else []


def subject_user(envelope: Envelope) -> UUID | None:
    if envelope.actor_user_id is not None:
        return envelope.actor_user_id
    if envelope.subject_type == "user" and envelope.subject_id:
        try:
            return UUID(envelope.subject_id)
        except ValueError:
            return None
    return None


class Triggers:
    def __init__(
        self,
        database: Database,
        gate: Gate,
        runner: Runner,
        types: EventTypeRegistry,
        config: Any,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.gate = gate
        self.runner = runner
        self.types = types
        self.config = config
        self.clock = clock
        self._live: tuple[float, list[Live]] | None = None

    def invalidate(self) -> None:
        self._live = None

    async def live(self) -> list[Live]:
        if self._live and time.monotonic() - self._live[0] < CACHE_SECONDS:
            return self._live[1]
        async with self.database.session() as session:
            rows = (
                await session.execute(
                    select(Automation, AutomationVersion)
                    .join(
                        AutomationVersion,
                        (AutomationVersion.automation_id == Automation.id)
                        & (AutomationVersion.version == Automation.published_version),
                    )
                    .where(Automation.state.in_(("active", "suspended")))
                )
            ).all()
        live = [Live(a.id, a.key, v.version, Definition.model_validate(v.definition)) for a, v in rows]
        self._live = (time.monotonic(), live)
        return live

    def consumer(self) -> Consumer:
        return Consumer(CONSUMER, frozenset({"*"}), self.handle, OWNER, replay_safe=False)

    async def handle(self, envelope: Envelope, ctx: ConsumerContext) -> None:
        if getattr(ctx, "replay", False) or not self.config().enabled:
            return
        for item in await self.live():
            trigger = item.definition.trigger
            if trigger.event_type != envelope.type:
                continue
            if not all(compare(envelope.payload.get(f.field), f.op, f.value) for f in trigger.filter):
                continue
            try:
                if trigger.kind == "event":
                    await self.fire(item, envelope)
                elif trigger.kind == "relative":
                    await self.schedule_relative(item, envelope)
            except Exception:
                log.exception("automation trigger failed", extra={"fields": {"automation": item.key}})

    async def fire(self, item: Live, envelope: Envelope | None, *, ref: dict[str, Any] | None = None) -> str:
        fields = event_fields(self.types, item.definition.trigger.event_type)
        trigger = TriggerInfo(
            ref=ref
            or {
                "type": envelope.type if envelope else "manual",
                "subject": f"{envelope.subject_type}:{envelope.subject_id}"
                if envelope and envelope.subject_id
                else None,
                "occurred_at": envelope.occurred_at.isoformat() if envelope else None,
            },
            chain_id=(envelope.correlation_id if envelope and envelope.correlation_id else None)
            or uuid4().hex,
            at=utc_now(self.clock),
            event_id=envelope.event_id if envelope else None,
            subject_user=subject_user(envelope) if envelope else None,
            path=lineage(envelope),
            scope=scope_of(envelope, item.key, fields),
            event=envelope,
        )
        async with self.database.unit_of_work() as uow:
            automation = await uow.session.get(Automation, item.id, with_for_update=True)
            if automation is None or automation.state not in ("active", "suspended"):
                return "ignored"
            admission = await self.gate.admit(uow.session, automation, item.version, item.definition, trigger)
        if admission.status != "running" or admission.execution_id is None:
            return admission.status
        outcome = await self.runner.run(admission.execution_id, item.definition, trigger)
        return outcome.status

    async def schedule_relative(self, item: Live, envelope: Envelope) -> None:
        trigger = item.definition.trigger
        raw = envelope.payload.get(trigger.reference or "")
        try:
            reference = raw if isinstance(raw, datetime) else datetime.fromisoformat(str(raw))
        except ValueError:
            return
        if reference.tzinfo is None:
            return
        fire_at = reference + timedelta(minutes=trigger.offset_minutes)
        async with self.database.unit_of_work() as uow:
            await uow.session.execute(
                insert(PendingFire)
                .values(
                    automation_id=item.id, source_event_id=envelope.event_id, fire_at=fire_at, fired=False
                )
                .on_conflict_do_nothing()
            )
