# Data Model — AI (schema `ai`)

## ai.conversations (owner-only, personal data class `content`)
`id` UUIDv7 · `user_id` FK `identity.users(id)` · `title` · `context` jsonb (page context ref, optional) · `created_at` · `updated_at` · `archived_at` null.

## ai.messages
`id` · `conversation_id` FK · `seq` · `role` (`user|assistant|tool`) · `content` text · `blocks` jsonb (tool calls, result summaries, `sources[]` with `class`/`as_of`, caveats) · `usage` jsonb (tokens, latency) · `created_at`. Unique `(conversation_id, seq)`. Raw tool results are **not** stored beyond summaries/source refs.

## ai.pending_actions
`id` · `user_id` FK · `conversation_id` FK · `tool` · `params` jsonb (redacted) · `params_hash` · `summary` (tool-generated) · `status` (`pending|confirmed|declined|expired|executed|failed`) · `created_at` · `expires_at` · `confirmed_at` null · `result_ref` null. Unique `(id)`; expiry job sets `expired`.

## ai.usage_daily (aggregate)
`user_id` FK · `day` · `tokens_in` · `tokens_out` · `requests` · `tool_calls` · PK `(user_id, day)`; no content.

## ai.diagnosis_executions (links 016 runs)
`diagnosis_run_id` (opaque) · `conversation_id` null · `status`.

## Registries (in memory) / Settings (020)
`AITool` registry, `LLMProvider` registry, `ExternalToolSource` registry (MCP). Settings: `ai.enabled`, `ai.provider.kind|endpoint|model` (+ `ai.provider.apiKey` secret), `ai.maxToolCallsPerTurn` (8), `ai.maxContextTokens`, `ai.requestTimeoutSeconds`, `ai.dailyTokenBudgetPerUser`, `ai.rateLimitPerMinute`, `ai.retentionDays` (90), `ai.pendingActionTtlMinutes` (10), `ai.autoNavigate` (false), `ai.tools.disabled[]`, `ai.mcp.servers[]` (`name`, `url`, secret ref, `allowlist[{tool, permission, sensitivity}]`).

## Events (via 007; no content)
Produced: `ai.conversation_started` (counts for stats, dedup `conversation_id`), `ai.action_confirmed|declined|expired` (dedup `pending_action_id`), `ai.provider_failed` (diagnostic, rate-limited). AI-performed domain actions are emitted by the owning domain with `actor_kind=ai`.

## Privacy / retention
Conversations/messages: owner-only; retention `ai.retentionDays`; user delete; erasure participant; excluded from admin views, logs and events. `pending_actions.params` redacted, purged after retention. Usage aggregates are non-personal metrics per user id (erased with account).
