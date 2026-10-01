# Contracts — AI

## Python capability `capabilities/ai`
- `register_ai_tool(AITool{name, description, params_schema, required_permission, sensitivity: read|write|sensitive|ai_forbidden, summarize(params)->str, handler(principal, params)->ToolResult})`. `ToolResult{state: ok|partial|stale|unavailable|error, data, sources[SourceRef{kind, ref, title, class: real|historical|knowledge, as_of}]}`.
- `LLMProvider` Protocol: `capabilities() -> {tools, streaming, max_context, json_mode}` · `async chat(messages, tools?, *, stream, max_tokens, timeout) -> AsyncIterator[LLMEvent]` · conformance kit; baseline `OpenAICompatibleProvider`.
- `ExternalToolSource` Protocol (MCP adapter): `list_tools() -> list[ExternalToolDef]`, `call(tool, args, principal_ctx)`; Admin allow-list mapping decides exposure.
- Implements: **`SearchAssistant`** (008: `stream(query, principal, result_refs)`, `interpret(text, principal, page_context)`), **`DiagnosisFlow`** executor for 016, optional **`EmbeddingProvider`** for 008.
- `Orchestrator.run_turn(principal, conversation, user_message, *, tool_policy) -> AsyncIterator[AIEvent]` (internal; used by chat, SearchAssistant, diagnosis with different tool policies).

## HTTP (`/api/v1`)
| Path | Permission | Notes |
|---|---|---|
| GET `/ai/status` | authenticated | `{available, provider_state}`; never blocks the UI |
| POST `/ai/conversations` · GET `/ai/conversations` · GET `/ai/conversations/{id}` · DELETE | `ai.use`, owner only | |
| POST `/ai/conversations/{id}/messages` (SSE) | `ai.use` | events: `delta`, `tool_call`, `tool_result`, `source`, `pending_action`, `done`, `error`; rate/budget enforced |
| GET `/ai/actions/{id}` · POST `/ai/actions/{id}/confirm` · `/decline` | owner only (session, CSRF, step-up if required) | confirm executes via `ConfirmationService`; idempotent |
| GET `/ai/tools` | `ai.use` | tools available to the caller (name, description, sensitivity) |
| PUT `/admin/ai/config` · POST `/admin/ai/provider/test` · GET `/admin/ai/usage` · GET/PUT `/admin/ai/mcp-servers` (+allowlist) | `ai.manage` (audited; secrets masked; **ai_forbidden for AI**) | metrics only, no content |
Problem codes: `ai.unavailable`, `ai.rate_limited`, `ai.budget_exceeded`, `ai.action_expired`, `ai.tool_forbidden`.

## Frontend
`AiEntry` (004 slot) + `<AiPanel>` (conversation, streaming, source chips, interpretation labelling, caveats), `<ConfirmationCard>` (tool-generated summary, confirm/decline, expiry countdown, keyboard accessible), `useSearchAssist` backend (008), diagnosis panel backend (016), admin AI settings screen.

## Tool ownership
Each domain registers its own tools in its own tasks (024 media tools, 011 wiki/news/calendar read tools, 016 ticket draft, 017 statistics, 006 services/health, 004 navigation suggestion, 008 global search). 018 ships the SDK, registry, orchestrator and conformance/injection suites.
