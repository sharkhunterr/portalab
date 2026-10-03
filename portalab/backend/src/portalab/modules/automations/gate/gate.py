"""Gate (T009, T025; R9-R11): admits a trigger into an execution, or records why not — never silently.

* idempotency: one execution per ``(automation, version, trigger event)`` (unique index);
* loops: the triggering event's provenance lists the ancestor automations (``path``); this automation
  among them, or a depth reaching ``automations.maxChainDepth`` ⇒ ``prevented`` (loop / depth); the chain
  id (= the events' ``correlation_id``) groups the whole cascade;
* repeats: ``dedup_key`` within ``dedup_window_s`` and ``cooldown_s`` ⇒ ``prevented``;
* storms: beyond the per-minute rate ⇒ coalesced into the latest execution (``batchable``, ``batch_count``)
  or recorded ``throttled``; a suspended automation records ``suspended``."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from portalab.core.ids import new_id
from portalab.modules.automations.definitions.schema import Definition
from portalab.modules.automations.definitions.substitution import substitute
from portalab.modules.automations.models import Automation, DedupWindow, Execution
from portalab.modules.automations.observability import metrics


@dataclass
class TriggerInfo:
    ref: dict[str, Any]
    chain_id: str
    at: datetime
    event_id: UUID | None = None
    subject_user: UUID | None = None
    path: list[str] = field(default_factory=list)  # ancestor automations (event provenance)
    scope: dict[str, Any] = field(default_factory=dict)  # substitution values (never stored)
    event: Any = None  # the envelope (never stored)


@dataclass(frozen=True, slots=True)
class Admission:
    execution_id: UUID | None
    status: str  # running | duplicate | batched | prevented | throttled | suspended
    depth: int = 0


class Gate:
    def __init__(self, config: Any) -> None:
        self.config = config  # callable → AutomationsConfig

    async def admit(
        self,
        session: AsyncSession,
        automation: Automation,
        version: int,
        definition: Definition,
        trigger: TriggerInfo,
    ) -> Admission:
        depth = len(trigger.path)
        status, error = "running", None
        if automation.state == "suspended":
            status, error = "suspended", "suspended"
        elif str(automation.id) in trigger.path:
            status, error = "prevented", "loop"
        elif depth >= self.config().max_chain_depth:
            status, error = "prevented", "depth"
        elif await self._repeated(session, automation, definition, trigger):
            status, error = "prevented", "dedup"
        elif await self._cooling(session, automation, definition, trigger.at):
            status, error = "prevented", "cooldown"
        else:
            rate = definition.limits.rate_per_min or self.config().default_rate_per_minute
            recent = int(
                await session.scalar(
                    select(func.count())
                    .select_from(Execution)
                    .where(
                        Execution.automation_id == automation.id,
                        Execution.started_at > trigger.at - timedelta(minutes=1),
                    )
                )
                or 0
            )
            if recent >= rate:
                if definition.limits.batchable:
                    latest = await session.scalar(
                        select(Execution.id)
                        .where(Execution.automation_id == automation.id)
                        .order_by(Execution.started_at.desc(), Execution.id.desc())
                        .limit(1)
                    )
                    if latest is not None:
                        await session.execute(
                            update(Execution)
                            .where(Execution.id == latest)
                            .values(batch_count=Execution.batch_count + 1)
                        )
                        metrics.increment("automations.batched")
                        return Admission(latest, "batched", depth)
                status, error = "throttled", "rate"
        execution_id = new_id()
        inserted = (
            await session.execute(
                insert(Execution)
                .values(
                    id=execution_id,
                    automation_id=automation.id,
                    version=version,
                    trigger_event_id=trigger.event_id,
                    trigger_ref={**trigger.ref, "path": trigger.path},
                    chain_id=trigger.chain_id,
                    depth=depth,
                    status=status,
                    principal=identity_ref(automation),
                    error_code=error,
                    started_at=trigger.at,
                    finished_at=None if status == "running" else trigger.at,
                )
                .on_conflict_do_nothing(
                    index_elements=["automation_id", "version", "trigger_event_id"],
                    index_where=Execution.trigger_event_id.is_not(None),
                )
                .returning(Execution.id)
            )
        ).scalar_one_or_none()
        if inserted is None:
            metrics.increment("automations.duplicates")
            return Admission(None, "duplicate", depth)
        if status != "running":
            metrics.increment(f"automations.gate.{error}")
        return Admission(inserted, status, depth)

    async def _repeated(
        self, session: AsyncSession, automation: Automation, definition: Definition, trigger: TriggerInfo
    ) -> bool:
        template = definition.limits.dedup_key
        if not template or not definition.limits.dedup_window_s:
            return False
        key = str(substitute(template, trigger.scope))[:200]
        expires = trigger.at + timedelta(seconds=definition.limits.dedup_window_s)
        statement = insert(DedupWindow).values(automation_id=automation.id, dedup_key=key, expires_at=expires)
        claimed = (
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[DedupWindow.automation_id, DedupWindow.dedup_key],
                    set_={"expires_at": expires},
                    where=DedupWindow.expires_at <= trigger.at,
                ).returning(DedupWindow.dedup_key)
            )
        ).scalar_one_or_none()
        return claimed is None

    async def _cooling(
        self, session: AsyncSession, automation: Automation, definition: Definition, at: datetime
    ) -> bool:
        if not definition.limits.cooldown_s:
            return False
        last = await session.scalar(
            select(func.max(Execution.started_at)).where(
                Execution.automation_id == automation.id,
                Execution.status.in_(("success", "running", "awaiting_approval")),
            )
        )
        return last is not None and at - last < timedelta(seconds=definition.limits.cooldown_s)


def identity_ref(automation: Automation) -> dict[str, Any]:
    return {
        "kind": automation.identity_kind,
        "user": str(automation.owner_user_id),
        "scopes": automation.system_scopes or [],
    }
