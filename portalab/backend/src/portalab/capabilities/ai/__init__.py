"""AI capability SDK (spec 018, contracts/ai-contracts.md).

* ``AITool`` — owners register tools that wrap **the same domain services** humans use. A tool declares the
  permission it needs and a sensitivity: ``read`` / ``write`` run when the acting user may; ``sensitive``
  never runs inline (a pending action the user confirms out-of-band); ``ai_forbidden`` never runs for the AI.
* ``ToolResult`` — state, data and sources (``real`` with ``as_of``, ``historical``, ``knowledge``).
* ``LLMProvider`` — chat with tool calling and streaming; the portal chooses no model.
* ``ExternalToolSource`` — MCP servers (e.g. MCParr), exposed only through an Admin allow-list.
* ``ai.invoke`` — the read-only text facade for automations (019).
* ``ai.perks`` — issue 173: what a member bought for the assistant in the shop (more tokens a day, a
  recharge, a stronger model, more reflection, a longer memory, reserved tools), granted per purchase.
* ``ai.models`` — a model server a connector reaches (issue 169: Ollama): its models, which are loaded, and
  the OpenAI-compatible address the assistant talks to.
The registry is owner-tagged: ``unregister(owner)`` removes a module's or plugin's tools.
"""

import re
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

from portalab.capabilities.registry import CapabilitySpec
from portalab.core.authz_port import Principal

INVOKE = "ai.invoke"
MODELS = "ai.models"
PERKS = "ai.perks"
Sensitivity = Literal["read", "write", "sensitive", "ai_forbidden"]
ResultState = Literal["ok", "partial", "stale", "unavailable", "error", "pending"]
SourceClass = Literal["real", "historical", "knowledge"]
_NAME = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


class AIError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SourceRef:
    kind: str
    ref: str
    title: str
    source_class: SourceClass = "real"
    as_of: datetime | None = None
    url: str | None = None
    # issue 171: what a card of the source shows beside the answer (never sent to the model): a picture of
    # the portal's own (a poster: ``/api/v1/…`` only) and a short line (« 2027 · movie »)
    image: str | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class ToolResult:
    state: ResultState = "ok"
    data: Any = None
    sources: Sequence[SourceRef] = ()
    detail: str = ""


Handler = Callable[[Principal, Mapping[str, Any]], Awaitable[ToolResult]]


def _default_summary(params: Mapping[str, Any]) -> str:
    return ", ".join(f"{k}={v}" for k, v in sorted(params.items()))[:300]


@dataclass(frozen=True, slots=True)
class AITool:
    name: str  # ``<domain>.<verb>``
    description: str
    params_schema: Mapping[str, Any]  # JSON Schema (object)
    required_permission: str
    sensitivity: Sensitivity
    handler: Handler = field(compare=False)
    summarize: Callable[[Mapping[str, Any]], str] = field(default=_default_summary, compare=False)
    owner: str = "core"
    version: int = 1


class AIToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, AITool] = {}

    def register(self, tool: AITool) -> AITool:
        if not _NAME.fullmatch(tool.name):
            raise AIError(f"tool name {tool.name!r} must look like '<domain>.<verb>'")
        if tool.params_schema.get("type") != "object":
            raise AIError(f"tool {tool.name!r} parameters must be a JSON Schema object")
        if tool.owner.startswith("plugin:") and not tool.name.startswith(tool.owner.split(":", 1)[1] + "."):
            raise AIError("plugin tools are namespaced '<plugin>.<verb>'")
        existing = self._tools.get(tool.name)
        if existing is not None and existing.owner != tool.owner:
            raise AIError(f"tool {tool.name!r} belongs to {existing.owner}")
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> AITool | None:
        return self._tools.get(name)

    def all(self) -> list[AITool]:
        return [self._tools[k] for k in sorted(self._tools)]

    def unregister(self, owner: str) -> int:
        doomed = [k for k, t in self._tools.items() if t.owner == owner]
        for key in doomed:
            del self._tools[key]
        return len(doomed)


default_ai_tools = AIToolRegistry()


def register_ai_tool(tool: AITool, registry: AIToolRegistry = default_ai_tools) -> AITool:
    return registry.register(tool)


# --- LLM provider -----------------------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: Sequence["ToolCall"] = ()
    tool_call_id: str | None = None
    name: str | None = None


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    parameters: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class LLMEvent:
    kind: Literal["delta", "tool_call", "usage", "done"]
    text: str = ""
    tool_call: ToolCall | None = None
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    tools: bool = True
    streaming: bool = True
    max_context: int = 8192
    json_mode: bool = False


class ProviderError(Exception):
    """The provider failed (unreachable, timeout, invalid answer); ``code`` is stable, never a secret."""

    def __init__(self, code: str = "provider_error") -> None:
        super().__init__(code)
        self.code = code


@runtime_checkable
class LLMProvider(Protocol):
    def capabilities(self) -> ProviderCapabilities: ...

    def chat(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec] = (),
        *,
        max_tokens: int = 1024,
        timeout: float = 60,
    ) -> AsyncIterator[LLMEvent]: ...


# --- external tool sources (MCP) ------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ExternalToolDef:
    name: str
    description: str
    input_schema: Mapping[str, Any]


@runtime_checkable
class ExternalToolSource(Protocol):
    name: str

    async def list_tools(self) -> Sequence[ExternalToolDef]: ...

    async def call(self, tool: str, arguments: Mapping[str, Any]) -> Any: ...


# --- automation facade (019) ----------------------------------------------------------------------------
@runtime_checkable
class AiInvoker(Protocol):
    async def invoke(self, instruction: str, principal: Principal, *, max_tokens: int = 400) -> str:
        """Read-only text drafting/classification as ``principal``; never a condition or sensitive input."""
        ...


INVOKE_SPEC = CapabilitySpec(
    name=INVOKE,
    version="1.0",
    protocol=AiInvoker,
    multi_provider=False,
    description="Read-only AI text generation for automations (018)",
)


@dataclass(frozen=True, slots=True)
class ModelInfo:
    """One model a server holds (issue 169) — what the administrators choose from."""

    name: str
    family: str | None = None
    parameters: str | None = None  # « 8.2B »
    quantization: str | None = None  # « Q4_K_M »
    size_bytes: int | None = None
    loaded: bool = False
    vram_bytes: int | None = None
    embedding: bool = False  # a model that turns text into vectors (semantic search), not a chat model
    tools: bool | None = (
        None  # whether it can call tools (the assistant needs it); None: the server does not say
    )


@runtime_checkable
class ModelServer(Protocol):
    def endpoint(self) -> str:
        """The OpenAI-compatible address of the server (``…/v1``) — what the assistant is pointed at."""
        ...

    async def models(self) -> Sequence[ModelInfo]: ...


MODELS_SPEC = CapabilitySpec(
    name=MODELS,
    version="1.0",
    protocol=ModelServer,
    multi_provider=True,
    description="A model server's models and its OpenAI-compatible address (issue 169: Ollama)",
)
# --- the assistant's capacities, sold in the shop (issue 173) ---------------------------------------------
# daily_tokens: more tokens each day (``amount``) · recharge: tokens once (``amount``), spent past the day's ·
# model: the administrators' stronger model · reflection: more reflection · context: a longer memory and more
# look-ups per answer · tools: the tools the administrators reserve. ``hours``: how long (0: for good; a
# recharge lasts until spent).
PERK_KINDS: tuple[str, ...] = ("daily_tokens", "recharge", "model", "reflection", "context", "tools")


@runtime_checkable
class AiPerks(Protocol):
    async def grant(self, user: UUID, perk: str, amount: int, hours: int, source_ref: str) -> bool:
        """Grant a perk (idempotent per ``source_ref``); ``False`` when the portal does not offer it."""
        ...

    async def revoke(self, source_ref: str) -> None: ...


PERKS_SPEC = CapabilitySpec(
    name=PERKS,
    version="1.0",
    protocol=AiPerks,
    multi_provider=False,
    description="The assistant's capacities a member bought in the shop (issue 173)",
)
SPECS: tuple[CapabilitySpec, ...] = (INVOKE_SPEC, MODELS_SPEC, PERKS_SPEC)
