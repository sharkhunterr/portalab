"""AI settings (T002), declared to Administration. The provider API key and MCP credentials are secrets."""

from dataclasses import dataclass, field
from typing import Any

from portalab.core.config_declaration import SettingCatalog, declare_setting, default_catalog

OWNER = "module:ai"
API_KEY = "ai.provider.apiKey"
MCP_TOKENS = "ai.mcp.tokens"


@dataclass(frozen=True, slots=True)
class AiConfig:
    enabled: bool = False
    provider_kind: str = "openai_compatible"
    provider_endpoint: str = ""
    provider_model: str = ""
    provider_reasoning: str = ""
    assistant_name: str = ""
    assistant_role: str = ""
    assistant_fallback: str = ""
    max_tool_calls_per_turn: int = 8
    max_context_tokens: int = 6000
    request_timeout_seconds: int = 60
    daily_token_budget_per_user: int = 50_000
    rate_limit_per_minute: int = 10
    retention_days: int = 90
    pending_action_ttl_minutes: int = 10
    auto_navigate: bool = False
    tools_disabled: list[str] = field(default_factory=list)
    mcp_servers: list[dict[str, Any]] = field(default_factory=list)
    embeddings_model: str = ""
    embeddings_dimension: int = 0


SETTINGS: dict[str, str] = {
    "enabled": "ai.enabled",
    "provider_kind": "ai.provider.kind",
    "provider_endpoint": "ai.provider.endpoint",
    "provider_model": "ai.provider.model",
    "provider_reasoning": "ai.provider.reasoning",
    "assistant_name": "ai.persona.name",
    "assistant_role": "ai.persona.role",
    "assistant_fallback": "ai.persona.fallback",
    "max_tool_calls_per_turn": "ai.maxToolCallsPerTurn",
    "max_context_tokens": "ai.maxContextTokens",
    "request_timeout_seconds": "ai.requestTimeoutSeconds",
    "daily_token_budget_per_user": "ai.dailyTokenBudgetPerUser",
    "rate_limit_per_minute": "ai.rateLimitPerMinute",
    "retention_days": "ai.retentionDays",
    "pending_action_ttl_minutes": "ai.pendingActionTtlMinutes",
    "auto_navigate": "ai.autoNavigate",
    "tools_disabled": "ai.tools.disabled",
    "mcp_servers": "ai.mcp.servers",
    "embeddings_model": "ai.embeddings.model",
    "embeddings_dimension": "ai.embeddings.dimension",
}
_DESCRIPTIONS = {
    "enabled": "Turn the assistant on (kill switch when off).",
    "provider_kind": "Provider adapter: openai_compatible (hosted APIs or local servers).",
    "provider_endpoint": "Base URL of the provider (e.g. http://ollama:11434/v1).",
    "provider_model": "Model name sent to the provider.",
    "assistant_name": "The assistant's name, told to the model and shown atop its window (empty: Assistant).",
    "assistant_role": "What the assistant is for on this portal (empty: the portal's own description).",
    "assistant_fallback": "What it does when its tools do not hold the answer (empty: a wiki page's link, "
    "else a support ticket).",
    "provider_reasoning": "How much a thinking model reflects before answering (none: at once — faster, and "
    "its thoughts never eat the answer's length); empty: the model's default.",
    "max_tool_calls_per_turn": "Maximum tool calls in one answer.",
    "max_context_tokens": "Approximate context window used for one answer.",
    "request_timeout_seconds": "Seconds before a provider call is abandoned.",
    "daily_token_budget_per_user": "Tokens one user may use per day.",
    "rate_limit_per_minute": "Messages one user may send per minute.",
    "retention_days": "Days conversations are kept.",
    "pending_action_ttl_minutes": "Minutes a proposed sensitive action waits for confirmation.",
    "auto_navigate": "Navigate automatically when the assistant suggests a page (off: shows a button).",
    "tools_disabled": "Assistant tools turned off on this portal.",
    "mcp_servers": "MCP servers (name, url, allowlist of {tool, permission, sensitivity}).",
    "embeddings_model": "Embedding model for semantic search (empty: semantic search off).",
    "embeddings_dimension": "Vector size of the embedding model.",
}


def declare_ai_settings(catalog: SettingCatalog = default_catalog) -> None:
    declare = declare_setting if catalog is default_catalog else catalog.declare
    known = {d.key for d in catalog.all()}
    defaults = AiConfig()
    schemas: dict[str, Any] = {"tools_disabled": list[str], "mcp_servers": list[dict[str, Any]]}
    for name, key in SETTINGS.items():
        if key not in known:
            default = getattr(defaults, name)
            declare(
                scope="global",
                key=key,
                schema=schemas.get(name, type(default)),
                default=default,
                owner=OWNER,
                description=_DESCRIPTIONS[name],
            )
    for key, schema, description in (
        (API_KEY, str | None, "Provider API key (secret)."),
        (MCP_TOKENS, dict[str, str] | None, "MCP server credentials by server name (secret)."),
    ):
        if key not in known:
            declare(
                scope="global",
                key=key,
                schema=schema,
                default=None,
                sensitive=True,
                owner=OWNER,
                description=description,
            )


declare_ai_settings()
