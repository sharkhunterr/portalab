"""Tool executor (T009): the only path from a model's tool call to a domain service.

1. the tool must be in the catalog offered **this turn** (a hallucinated or unpermitted name is refused
   with ``ai.tool_forbidden`` — nothing reveals whether it exists);
2. parameters are validated against the tool's JSON Schema;
3. the AI principal is **re-authorized** right before the call;
4. ``sensitive`` tools never run inline: a pending action is created for the user to confirm;
5. results are redacted and size-capped; failures become ``error``/``unavailable`` results."""

import asyncio
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from portalab.capabilities.ai import AITool, ToolCall, ToolResult
from portalab.core.authz_port import Authorizer, Principal
from portalab.core.logging import get_logger
from portalab.modules.ai.observability import metrics
from portalab.modules.ai.pending import PendingActions, PendingView
from portalab.modules.ai.principal import ai_principal
from portalab.modules.ai.redaction import cap, redact

log = get_logger("portalab.ai")
TOOL_TIMEOUT = 15.0


@dataclass(frozen=True, slots=True)
class Execution:
    call: ToolCall
    tool: AITool | None
    result: ToolResult
    pending: PendingView | None = None
    code: str | None = None  # ``ai.tool_forbidden`` / ``invalid_parameters`` / …


def validation_errors(schema: Mapping[str, Any], params: Mapping[str, Any]) -> list[str]:
    try:
        validator = Draft202012Validator(dict(schema))
        return [e.message[:200] for e in validator.iter_errors(dict(params))][:5]
    except SchemaError:
        return ["invalid tool schema"]


class ToolExecutor:
    def __init__(
        self, authorizer: Authorizer, pending: PendingActions, *, timeout: float = TOOL_TIMEOUT
    ) -> None:
        self.authorizer = authorizer
        self.pending = pending
        self.timeout = timeout

    async def execute(
        self,
        principal: Principal,
        call: ToolCall,
        offered: Mapping[str, AITool],
        *,
        conversation_id: UUID | None = None,
    ) -> Execution:
        tool = offered.get(call.name)
        if tool is None:
            metrics.increment("ai.tools.forbidden")
            return Execution(
                call, None, ToolResult("error", detail="ai.tool_forbidden"), code="ai.tool_forbidden"
            )
        errors = validation_errors(tool.params_schema, call.arguments)
        if errors:
            metrics.increment("ai.tools.invalid")
            return Execution(
                call,
                tool,
                ToolResult("error", {"errors": errors}, detail="invalid_parameters"),
                code="invalid_parameters",
            )
        acting = ai_principal(principal)
        try:
            allowed = await self.authorizer.is_allowed(acting, tool.required_permission)
        except Exception:
            allowed = False
        if not allowed:
            metrics.increment("ai.tools.forbidden")
            return Execution(
                call, None, ToolResult("error", detail="ai.tool_forbidden"), code="ai.tool_forbidden"
            )
        if tool.sensitivity == "sensitive":
            view = await self.pending.create(
                principal, tool, dict(call.arguments), conversation_id=conversation_id
            )
            metrics.increment("ai.pending.created")
            return Execution(
                call,
                tool,
                ToolResult(
                    "pending",
                    {
                        "action_id": str(view.id),
                        "summary": view.summary,
                        "status": "awaiting_user_confirmation",
                    },
                    detail="The user must confirm this action in the portal; it has not been performed.",
                ),
                pending=view,
            )
        return Execution(call, tool, await self.run(tool, acting, call.arguments))

    async def run(self, tool: AITool, acting: Principal, params: Mapping[str, Any]) -> ToolResult:
        started = time.monotonic()
        try:
            result = await asyncio.wait_for(tool.handler(acting, dict(params)), timeout=self.timeout)
        except TimeoutError:
            metrics.increment("ai.tools.timeout")
            return ToolResult("unavailable", detail="timeout")
        except Exception as exc:
            metrics.increment("ai.tools.error")
            log.warning("ai tool failed", extra={"fields": {"tool": tool.name, "error": type(exc).__name__}})
            code = getattr(exc, "code", None)
            return ToolResult("error", detail=str(code) if isinstance(code, str) else "tool_failed")
        finally:
            metrics.observe("ai.tools.latency_ms", (time.monotonic() - started) * 1000)
        if not isinstance(result, ToolResult):
            return ToolResult("error", detail="invalid_tool_result")
        metrics.increment(f"ai.tools.outcome.{result.state}")
        return ToolResult(
            result.state, cap(redact(result.data)), tuple(result.sources)[:20], result.detail[:300]
        )
