"""Admin API (T030, T031): provider and limits, provider test, usage (metrics only — never content) and the
MCP allow-list. All routes need ``ai.manage`` (sensitive, audited) — a permission the assistant itself can
never use (``ai_forbidden``). Secrets are write-only: responses only say whether one is set."""

import time
from typing import Annotated, Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from portalab.capabilities.administration import CONFIG_WRITER_CAPABILITY
from portalab.capabilities.ai import ChatMessage, ProviderError
from portalab.core.audit_port import AuditRecord
from portalab.core.authorization import require
from portalab.core.authz_port import Principal, ResourceRef
from portalab.core.errors import Unavailable, ValidationFailed
from portalab.modules.ai.api.router import Module
from portalab.modules.ai.permissions import AI_MANAGE
from portalab.modules.ai.settings import API_KEY, MCP_TOKENS, SETTINGS

router = APIRouter(prefix="/api/v1", tags=["ai-admin"])
Manager = Annotated[Principal, require(AI_MANAGE)]


class AiConfigIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    provider_kind: Literal["openai_compatible"] | None = None
    provider_endpoint: str | None = Field(default=None, max_length=500, pattern=r"^(https?://\S+)?$")
    provider_model: str | None = Field(default=None, max_length=200)
    provider_secret: str | None = Field(default=None, max_length=500)  # write-only; "" clears
    max_tool_calls_per_turn: int | None = Field(default=None, ge=0, le=20)
    max_context_tokens: int | None = Field(default=None, ge=1000, le=1_000_000)
    request_timeout_seconds: int | None = Field(default=None, ge=5, le=600)
    daily_token_budget_per_user: int | None = Field(default=None, ge=0, le=100_000_000)
    rate_limit_per_minute: int | None = Field(default=None, ge=1, le=600)
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    pending_action_ttl_minutes: int | None = Field(default=None, ge=1, le=1440)
    auto_navigate: bool | None = None
    tools_disabled: list[str] | None = Field(default=None, max_length=500)
    embeddings_model: str | None = Field(default=None, max_length=200)
    embeddings_dimension: int | None = Field(default=None, ge=0, le=8192)


class AiAdminToolOut(BaseModel):
    name: str
    owner: str
    permission: str
    sensitivity: str
    disabled: bool


class AiConfigOut(BaseModel):
    values: dict[str, Any]
    provider_secret_set: bool
    available: bool
    tools: list[AiAdminToolOut]


class AiProviderTestOut(BaseModel):
    ok: bool
    latency_ms: int
    code: str | None = None


class AiUsageOut(BaseModel):
    days: list[dict[str, Any]]
    metrics: dict[str, float]


class McpAllowEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: str = Field(min_length=1, max_length=120)
    permission: str = Field(min_length=3, max_length=128)
    sensitivity: Literal["read", "write", "sensitive"] = "sensitive"


class McpServerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")
    url: str = Field(max_length=500, pattern=r"^https?://\S+$")
    allowlist: list[McpAllowEntry] = Field(default_factory=list, max_length=200)


class McpServersIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    servers: list[McpServerIn] = Field(max_length=20)
    credentials: dict[str, str | None] = Field(default_factory=dict)  # write-only; null removes


class McpServerOut(BaseModel):
    name: str
    url: str
    allowlist: list[dict[str, Any]]
    credential_set: bool
    state: str
    discovered_tools: list[str]


async def _writer(module: Any) -> Any:
    providers = module.capabilities.system_providers(CONFIG_WRITER_CAPABILITY)
    if not providers:
        raise Unavailable("Settings cannot be changed right now.", code="admin.unavailable")
    return providers[0].provider


def _config_out(module: Any) -> AiConfigOut:
    disabled = set(module.config.tools_disabled)
    values = {name: getattr(module.config, name) for name in SETTINGS if name != "mcp_servers"}
    return AiConfigOut(
        values=values,
        provider_secret_set=bool(module.api_key),
        available=module.available(),
        tools=[
            AiAdminToolOut(
                name=t.name,
                owner=t.owner,
                permission=t.required_permission,
                sensitivity=t.sensitivity,
                disabled=t.name in disabled,
            )
            for t in module.catalog.all()
        ],
    )


@router.get("/admin/ai/config", response_model=AiConfigOut)
async def get_config(_: Manager, module: Module) -> AiConfigOut:
    return _config_out(module)


@router.put("/admin/ai/config", response_model=AiConfigOut)
async def put_config(principal: Manager, body: AiConfigIn, module: Module) -> AiConfigOut:
    writer = await _writer(module)
    changes = body.model_dump(exclude_unset=True)
    secret = changes.pop("provider_secret", None)
    for name, value in changes.items():
        if value is not None:
            await writer.set_global(principal, SETTINGS[name], value, reason="ai admin")
    if "provider_secret" in body.model_fields_set:
        await writer.set_global(principal, API_KEY, secret or None, reason="ai admin")
    await module.refresh_config()
    return _config_out(module)


@router.post("/admin/ai/provider/test", response_model=AiProviderTestOut)
async def test_provider(principal: Manager, module: Module) -> AiProviderTestOut:
    started = time.monotonic()
    code: str | None = None
    provider = module.provider()
    if provider is None:
        code = "not_configured"
    else:
        try:
            async for _ in provider.chat(
                [ChatMessage("user", "Reply with OK.")], (), max_tokens=5, timeout=15
            ):
                pass
        except ProviderError as exc:
            code = exc.code
        except Exception:
            code = "provider_error"
    latency = int((time.monotonic() - started) * 1000)
    async with module.database.unit_of_work() as uow:
        await module.pending.audit.record(
            uow.session,
            AuditRecord(
                action="ai.provider_tested",
                actor=principal,
                resource=ResourceRef("ai_provider", module.config.provider_kind),
                result="success" if code is None else "failure",
                context={"code": code or "ok"},
                sensitive=True,
            ),
        )
    return AiProviderTestOut(ok=code is None, latency_ms=latency, code=code)


class AiModelOut(BaseModel):
    name: str
    family: str | None
    parameters: str | None
    quantization: str | None
    size_bytes: int | None
    loaded: bool
    vram_bytes: int | None
    embedding: bool
    tools: bool | None


class AiServerOut(BaseModel):
    service_id: str
    name: str
    connector: str
    endpoint: str
    state: str
    models: list[AiModelOut]


@router.get("/admin/ai/servers", response_model=list[AiServerOut])
async def model_servers(_: Manager, module: Module) -> list[dict[str, Any]]:
    """Issue 169: the model servers of the connected services (Ollama) — where to point the assistant, which
    model to choose, what is in memory."""
    return await module.servers()


@router.get("/admin/ai/usage", response_model=AiUsageOut)
async def usage(_: Manager, module: Module) -> AiUsageOut:
    from portalab.modules.ai.observability import metrics

    return AiUsageOut(days=await module.governor.usage(30), metrics=metrics.snapshot())


def _servers_out(module: Any) -> list[McpServerOut]:
    states, discovered = module.mcp.states(), module.mcp.discovered()
    return [
        McpServerOut(
            name=str(s.get("name")),
            url=str(s.get("url")),
            allowlist=list(s.get("allowlist") or []),
            credential_set=bool(module.mcp_tokens.get(str(s.get("name")))),
            state=states.get(str(s.get("name")), "unknown"),
            discovered_tools=discovered.get(str(s.get("name")), []),
        )
        for s in module.config.mcp_servers
    ]


@router.get("/admin/ai/mcp-servers", response_model=list[McpServerOut])
async def get_mcp(_: Manager, module: Module) -> list[McpServerOut]:
    await module.mcp.refresh(force=True)
    return _servers_out(module)


@router.put("/admin/ai/mcp-servers", response_model=list[McpServerOut])
async def put_mcp(principal: Manager, body: McpServersIn, module: Module) -> list[McpServerOut]:
    names = [s.name for s in body.servers]
    if len(set(names)) != len(names):
        raise ValidationFailed("Server names must be unique.", code="ai.mcp_duplicate")
    writer = await _writer(module)
    await writer.set_global(
        principal, SETTINGS["mcp_servers"], [s.model_dump() for s in body.servers], reason="ai admin"
    )
    if body.credentials:
        tokens = {k: v for k, v in module.mcp_tokens.items() if k in names}
        for name, value in body.credentials.items():
            if name not in names:
                continue
            if value:
                tokens[name] = value
            else:
                tokens.pop(name, None)
        await writer.set_global(principal, MCP_TOKENS, tokens or None, reason="ai admin")
    await module.refresh_config()
    await module.mcp.refresh(force=True)
    return _servers_out(module)
