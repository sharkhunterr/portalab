"""``communication.produce`` (T024; R1): the Automations (019) action that produces a communication through
the same producer — under the **author's** authority (the automation principal acts for its author), with
the trigger's dedup key. 010 contains no rule engine."""

from collections.abc import Awaitable, Callable, Mapping
from typing import Any
from uuid import UUID

from portalab.capabilities.automation_actions import ActionRegistry, ActionType, default_actions
from portalab.capabilities.notifications import (
    AllAuthenticated,
    AudienceSpec,
    CommunicationRef,
    CommunicationRequest,
    Role,
    Users,
    WithPermission,
)
from portalab.core.authz_port import Principal
from portalab.core.errors import ValidationFailed
from portalab.modules.notifications.permissions import SEND_TO_AUDIENCE

KEY = "communication.produce"
Send = Callable[[CommunicationRequest, Principal | None], Awaitable[CommunicationRef]]


def parse_audience(raw: Mapping[str, Any]) -> AudienceSpec:
    kind = raw.get("type")
    if kind == "users":
        return Users(tuple(UUID(str(u)) for u in raw.get("ids", [])))
    if kind == "permission":
        return WithPermission(str(raw["permission"]))
    if kind == "role":
        return Role(str(raw["role"]))
    if kind == "all":
        return AllAuthenticated()
    raise ValidationFailed("Unknown audience.", code="notifications.invalid")


def register_action(send: Send, registry: ActionRegistry = default_actions) -> None:
    async def run(params: Mapping[str, Any], principal: Principal) -> Mapping[str, Any]:
        ref = await send(
            CommunicationRequest(
                category=str(params["category"]),
                template_key=str(params["template_key"]),
                audience=parse_audience(params["audience"]),
                dedup_key=str(params["dedup_key"]),
                kind=params.get("kind", "notification"),
                priority=params.get("priority", "normal"),
                params=dict(params.get("params") or {}),
                source="automation",
                source_ref=str(params.get("rule", "")) or None,
                action_url=params.get("action_url"),
            ),
            principal,
        )
        return {"communication": str(ref.id), "created": ref.created, "recipients": ref.recipients}

    if registry.get(KEY) is None:
        registry.register(
            ActionType(
                key=KEY,
                description="Send a notification or alert to an audience",
                permission=SEND_TO_AUDIENCE,
                idempotency="dedup_key from the trigger: one communication per (source, dedup_key)",
                run=run,
                owner="module:notifications",
                required=("category", "template_key", "audience", "dedup_key"),
                ai_output_allowed=True,
                params_schema={
                    "category": "string",
                    "template_key": "string",
                    "audience": "object {type: users|permission|role|all, …}",
                    "dedup_key": "string",
                    "kind": "notification|alert",
                    "priority": "low|normal|high|critical",
                    "params": "object? (template values)",
                    "action_url": "string? (in-portal route)",
                    "rule": "string? (source reference)",
                },
            )
        )
