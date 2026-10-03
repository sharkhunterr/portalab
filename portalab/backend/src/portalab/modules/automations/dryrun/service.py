"""Dry run (T029; R14): evaluates the conditions on a sample event and plans each step — action, current
permission, approval need, parameters after substitution — with **no side effects** (no execution row, no
handler call, no event)."""

from datetime import datetime
from typing import Any
from uuid import uuid4

from portalab.capabilities.automation_actions import ActionRegistry
from portalab.capabilities.automations import LeafContext
from portalab.capabilities.events import Envelope, EventTypeRegistry
from portalab.core.permissions import PermissionRegistry
from portalab.modules.automations.definitions.schema import Definition
from portalab.modules.automations.definitions.substitution import substitute
from portalab.modules.automations.definitions.validate import effective_sensitivity, event_fields
from portalab.modules.automations.evaluator.evaluator import Evaluator
from portalab.modules.automations.identity.guard import IdentityGuard, principal_of
from portalab.modules.automations.models import Automation
from portalab.modules.automations.triggers.consumer import scope_of, subject_user


async def dry_run(
    automation: Automation,
    definition: Definition,
    sample: dict[str, Any],
    *,
    at: datetime,
    evaluator: Evaluator,
    guard: IdentityGuard,
    actions: ActionRegistry,
    permissions: PermissionRegistry,
    types: EventTypeRegistry,
    standing: list[str],
) -> dict[str, Any]:
    event_type = str(sample.get("event_type") or definition.trigger.event_type or "manual")
    actor = sample.get("actor_user_id")
    envelope = Envelope(
        event_id=uuid4(),
        seq=0,
        type=event_type,
        type_version=1,
        occurred_at=at,
        received_at=at,
        source_system="dry-run",
        source_event_id=None,
        actor_user_id=actor,
        actor_kind="user",
        subject_type=sample.get("subject_type"),
        subject_id=sample.get("subject_id"),
        payload=dict(sample.get("payload") or {}),
        provenance={},
        correlation_id=None,
    )
    ctx = LeafContext(principal_of(automation), at, envelope, subject_user(envelope))
    passed, trace = await evaluator.evaluate(definition.conditions, ctx)
    scope = scope_of(envelope, automation.key, event_fields(types, definition.trigger.event_type))
    plan: list[dict[str, Any]] = []
    for step in definition.steps:
        action = actions.get(step.action)
        if action is None:
            plan.append({"id": step.id, "action": step.action, "status": "missing"})
            continue
        sensitivity = effective_sensitivity(action, permissions)
        plan.append(
            {
                "id": step.id,
                "action": step.action,
                "allowed": await guard.allowed(automation, action),
                "sensitivity": sensitivity,
                "approval": sensitivity == "destructive"
                or (sensitivity == "sensitive" and action.key not in standing),
                "params": substitute(step.params, scope, keep_missing=True),
            }
        )
    return {
        "conditions_passed": passed,
        "trace": trace,
        "steps": plan if passed else [],
        "planned_if_passed": plan,
    }
