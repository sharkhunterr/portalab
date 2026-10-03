"""Runner (T010, T013, T016, T025): executes one admitted execution.

Conditions are evaluated (trace kept); then each step: the action must exist; the identity must be allowed
**now** (else ``refused`` + ``needs_review``); a *destructive* action — or a *sensitive* one without a
standing approval attested at publish — stops at an approval request (``awaiting_approval``); otherwise the
handler runs with the per-action timeout inside the execution deadline, under ``action_context`` and the
chain's correlation id (events it emits carry ``chain_id``). Failures follow ``on_error``; results keep
references only. Finished executions feed the auto-suspender."""

import asyncio
import hashlib
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID

from portalab.capabilities.automation_actions import ActionContext, ActionRegistry, action_context
from portalab.capabilities.automations import LeafContext
from portalab.core.db import Database
from portalab.core.event_port import SubjectRef, provenance_scope
from portalab.core.logging import correlation_scope
from portalab.core.permissions import PermissionRegistry
from portalab.core.time import Clock, utc_now
from portalab.modules.automations.definitions.schema import Definition, Step
from portalab.modules.automations.definitions.substitution import substitute
from portalab.modules.automations.definitions.validate import effective_sensitivity
from portalab.modules.automations.evaluator.evaluator import Evaluator
from portalab.modules.automations.gate.gate import TriggerInfo
from portalab.modules.automations.identity.guard import IdentityGuard, principal_of
from portalab.modules.automations.models import Approval, Automation, AutomationVersion, Execution
from portalab.modules.automations.observability import log, metrics
from portalab.modules.automations.suspender.suspender import Suspender

REF_TYPES = (str, int, bool)


def params_hash(action: str, params: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps({"action": action, "params": params}, sort_keys=True, default=str).encode()
    ).hexdigest()


def result_refs(result: Mapping[str, Any] | None) -> dict[str, Any]:
    """Only short scalar references are kept (ids, counts, flags) — never bodies."""
    return {
        str(k)[:40]: v
        for k, v in (result or {}).items()
        if isinstance(v, REF_TYPES) and (not isinstance(v, str) or len(v) <= 80)
    }


@dataclass
class Outcome:
    status: str
    error: str | None = None


class Runner:
    def __init__(
        self,
        database: Database,
        actions: ActionRegistry,
        permissions: PermissionRegistry,
        guard: IdentityGuard,
        evaluator: Evaluator,
        suspender: Suspender,
        config: Any,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.database = database
        self.actions = actions
        self.permissions = permissions
        self.guard = guard
        self.evaluator = evaluator
        self.suspender = suspender
        self.config = config
        self.clock = clock

    async def run(self, execution_id: UUID, definition: Definition, trigger: TriggerInfo) -> Outcome:
        async with self.database.session() as session:
            execution = await session.get(Execution, execution_id)
            assert execution is not None
            automation = await session.get(Automation, execution.automation_id)
            version = await session.get(AutomationVersion, (execution.automation_id, execution.version))
        assert automation is not None and version is not None
        ctx = LeafContext(principal_of(automation), trigger.at, trigger.event, trigger.subject_user)
        passed, trace = await self.evaluator.evaluate(definition.conditions, ctx)
        if not passed:
            return await self.finish(execution_id, "no_op", trace=trace)
        return await self.steps(
            execution_id,
            automation,
            version.standing_approvals,
            definition.steps,
            dict(trigger.scope),
            trace,
            execution.depth,
            execution.chain_id,
            path=list(execution.trigger_ref.get("path", [])),
        )

    async def steps(
        self,
        execution_id: UUID,
        automation: Automation,
        standing: list[str],
        steps: list[Step],
        scope: dict[str, Any],
        trace: list[dict[str, Any]] | None,
        depth: int,
        chain_id: str,
        *,
        path: list[str] | None = None,
        approved: str | None = None,
        done: list[dict[str, Any]] | None = None,
    ) -> Outcome:
        config = self.config()
        path = list(path or [])
        deadline = time.monotonic() + config.execution_timeout_seconds
        results: list[dict[str, Any]] = list(done or [])
        for index, step in enumerate(steps):
            action = self.actions.get(step.action)
            if action is None:
                results.append(
                    {"id": step.id, "action": step.action, "status": "failed", "error_code": "action_missing"}
                )
                if step.on_error == "stop":
                    return await self.finish(
                        execution_id, "failed", trace=trace, steps=results, error="action_missing"
                    )
                continue
            if not await self.guard.allowed(automation, action):
                results.append(
                    {"id": step.id, "action": step.action, "status": "refused", "error_code": "forbidden"}
                )
                await self.flag_review(automation.id)
                return await self.finish(
                    execution_id, "refused", trace=trace, steps=results, error="action_forbidden"
                )
            params = substitute(step.params, scope)
            sensitivity = effective_sensitivity(action, self.permissions)
            needs_approval = sensitivity == "destructive" or (
                sensitivity == "sensitive" and action.key not in standing
            )
            if needs_approval and approved != step.id:
                await self.request_approval(
                    execution_id, automation, step, action.key, params, steps[index:], scope
                )
                results.append({"id": step.id, "action": step.action, "status": "awaiting_approval"})
                return await self.finish(
                    execution_id, "awaiting_approval", trace=trace, steps=results, final=False
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                results.append({"id": step.id, "action": step.action, "status": "timeout"})
                return await self.finish(
                    execution_id, "timeout", trace=trace, steps=results, error="execution_timeout"
                )
            started = time.monotonic()
            context = ActionContext(automation.id, execution_id, chain_id, depth, step.id)
            lineage = {
                "automation": {
                    "id": str(automation.id),
                    "execution_id": str(execution_id),
                    "depth": depth,
                    "path": [*path, str(automation.id)],
                }
            }
            try:
                with action_context(context), correlation_scope(chain_id), provenance_scope(lineage):
                    result = await asyncio.wait_for(
                        action.run(params, principal_of(automation)),
                        min(config.action_timeout_seconds, remaining),
                    )
            except TimeoutError:
                results.append(
                    {"id": step.id, "action": step.action, "status": "timeout", "duration_ms": _ms(started)}
                )
                return await self.finish(
                    execution_id, "timeout", trace=trace, steps=results, error="action_timeout"
                )
            except Exception as exc:
                code = getattr(exc, "code", None)
                error = code if isinstance(code, str) else type(exc).__name__
                log.warning(
                    "automation step failed", extra={"fields": {"action": step.action, "error": error}}
                )
                results.append(
                    {
                        "id": step.id,
                        "action": step.action,
                        "status": "failed",
                        "error_code": error[:64],
                        "duration_ms": _ms(started),
                    }
                )
                if step.on_error == "stop":
                    return await self.finish(
                        execution_id, "failed", trace=trace, steps=results, error=error[:64]
                    )
                continue
            for key, value in (result or {}).items():
                scope[f"steps.{step.id}.{key}"] = value
            results.append(
                {
                    "id": step.id,
                    "action": step.action,
                    "status": "ok",
                    "duration_ms": _ms(started),
                    "result": result_refs(result),
                }
            )
            approved = None
        failed = any(r["status"] == "failed" for r in results)
        return await self.finish(
            execution_id, "success", trace=trace, steps=results, error="step_failed" if failed else None
        )

    async def request_approval(
        self,
        execution_id: UUID,
        automation: Automation,
        step: Step,
        action_key: str,
        params: Mapping[str, Any],
        remaining: list[Step],
        scope: Mapping[str, Any],
    ) -> None:
        action = self.actions.get(action_key)
        summary = (
            action.summarize(params)
            if action and action.summarize
            else f"{action_key}: {json.dumps(params, default=str)[:300]}"
        )
        pending = [
            {
                "id": s.id,
                "action": s.action,
                "on_error": s.on_error,
                "params": substitute(s.params, scope, keep_missing=True),
            }
            for s in remaining
        ]
        now = utc_now(self.clock)
        async with self.database.unit_of_work() as uow:
            uow.session.add(
                Approval(
                    execution_id=execution_id,
                    step_id=step.id,
                    action=action_key,
                    summary=summary[:400],
                    params_hash=params_hash(action_key, params),
                    params={"steps": pending, "approved_params": dict(params)},
                    status="pending",
                    created_at=now,
                    expires_at=now + timedelta(hours=self.config().approval_ttl_hours),
                )
            )
            events = getattr(self.suspender, "events", None)
            if events is not None:
                await events.publish(
                    uow.session,
                    "automation.approval_requested",
                    {"automation": automation.key, "action": action_key},
                    occurred_at=now,
                    subject=SubjectRef("automation", str(automation.id)),
                    dedup_key=f"automation.approval_requested:{execution_id}:{step.id}",
                )
        metrics.increment("automations.approvals.requested")

    async def flag_review(self, automation_id: UUID) -> None:
        async with self.database.unit_of_work() as uow:
            automation = await uow.session.get(Automation, automation_id, with_for_update=True)
            if automation is not None:
                automation.needs_review = True

    async def finish(
        self,
        execution_id: UUID,
        status: str,
        *,
        trace: list[dict[str, Any]] | None = None,
        steps: list[dict[str, Any]] | None = None,
        error: str | None = None,
        final: bool = True,
    ) -> Outcome:
        suspended: Automation | None = None
        async with self.database.unit_of_work() as uow:
            execution = await uow.session.get(Execution, execution_id, with_for_update=True)
            assert execution is not None
            execution.status = status
            if trace is not None:
                execution.conditions_trace = trace
            if steps is not None:
                execution.steps = steps
            execution.error_code = error
            if final:
                execution.finished_at = utc_now(self.clock)
                automation = await uow.session.get(Automation, execution.automation_id, with_for_update=True)
                if automation is not None and await self.suspender.record(uow.session, automation, status):
                    suspended = automation
        if suspended is not None:
            await self.suspender.notify(suspended)
        metrics.increment(f"automations.executions.{status}")
        return Outcome(status, error)


def _ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
