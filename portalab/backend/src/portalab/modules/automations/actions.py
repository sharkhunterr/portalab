"""Engine-owned actions (T023): only what no domain owns — ``approval.request`` (an explicit human approval
gate inside the step list) and ``automation.trigger`` (an internal ``automation.triggered`` event that other
automations may react to, bounded by the same chain/loop rules). Domain actions are registered by their
owners (010 ``communication.produce``, 013 ``award.*``/``reward.unlock``, 016 tickets/incidents, 011
``content.publish``, 005 ``connector.*``, 018 ``ai.invoke``)."""

from collections.abc import Mapping
from typing import Any

from portalab.capabilities.automation_actions import ActionRegistry, ActionType, current_action
from portalab.core.authz_port import Principal
from portalab.core.db import Database
from portalab.core.event_port import EventPublisher, SubjectRef
from portalab.core.time import Clock, utc_now
from portalab.modules.automations.permissions import MANAGE

OWNER = "module:automations"


def register_engine_actions(
    registry: ActionRegistry, database: Database, events: EventPublisher, *, clock: Clock | None = None
) -> None:
    async def approval(params: Mapping[str, Any], principal: Principal) -> Mapping[str, Any]:
        return {"approved": True}  # reached only once an approver approved this step

    async def trigger(params: Mapping[str, Any], principal: Principal) -> Mapping[str, Any]:
        context = current_action()
        async with database.unit_of_work() as uow:
            result = await events.publish(
                uow.session,
                "automation.triggered",
                {
                    "automation": str(params["automation"])[:64],
                    "payload": str(params.get("payload", ""))[:200] or None,
                },
                occurred_at=utc_now(clock),
                actor=principal,
                subject=SubjectRef("automation", str(context.automation_id)) if context else None,
                dedup_key=f"automation.triggered:{context.execution_id}:{context.step_id}"
                if context
                else None,
            )
        return {"event": str(result.event_id)}

    if registry.get("approval.request") is None:
        registry.register(
            ActionType(
                key="approval.request",
                description="Wait for a human approval before the next steps",
                permission=MANAGE,
                idempotency="one approval per execution and step",
                run=approval,
                owner=OWNER,
                params_schema={"summary": "string"},
                sensitivity="destructive",
                summarize=lambda p: str(p.get("summary", "Approval requested"))[:300],
            )
        )
    if registry.get("automation.trigger") is None:
        registry.register(
            ActionType(
                key="automation.trigger",
                description="Trigger automations listening to automation.triggered (chain-limited)",
                permission=MANAGE,
                idempotency="dedup per execution and step",
                run=trigger,
                owner=OWNER,
                params_schema={"automation": "string", "payload": "string?"},
                ai_output_allowed=True,
            )
        )
