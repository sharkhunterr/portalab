# Implementation Plan: AI Capability

**Branch**: `018-ai-capability` | **Date**: 2026-10-01 | **Spec**: `specs/018-ai-capability/spec.md`
**Roadmap**: Phase 5 step 18 *AI*. Plugs into planned ports: 008 (`SearchAssistant`, `EmbeddingProvider`), 016 (`DiagnosisFlow`), 003 (principal/`ConfirmationService`/audit), 005-style secrets/HTTP, and the tool tasks already listed in 024/011/016/017/006.

## Summary
The AI is a **cross-cutting capability** (small module `ai` + SDK) that never holds more rights than the user: an orchestrator drives an `LLMProvider` (OpenAI-compatible baseline, no model chosen) with a **permission-filtered, re-authorized tool registry** whose tools wrap the same domain services humans use. Sensitive tools never run inline — they create tool-summarized pending actions confirmed out-of-band by the user's own session. Answers carry validated source attribution, conversations are owner-only, MCParr/MCP tools are an optional, default-deny allow-listed source, and every AI failure is isolated from classic features.

## Technical Context
**Language**: Python 3.12 + TypeScript/React 19 · **Deps (new)**: `httpx` (already via connectors), `mcp` (official MCP client SDK, optional extra), `jsonschema` (tool params) · **Storage**: schema `ai` · **Testing**: pytest with a scripted fake `LLMProvider`, injection corpus, conformance kits; Vitest; Playwright · **Constraints**: authorization independent of model output, confirmation out-of-band, no secrets in prompts/logs/audit, SSE streaming, provider-agnostic · **Scale**: personal/community usage with budgets.

## Constitution Check — PASS
XVI/XVII AI bounded + independent of classic features · VI default-deny, confirmation, secrets · VII privacy (owner-only conversations) · II/XX no second business path/search/stat/notification engine · III extensible tools, providers, external sources · IX graceful degradation · XIII audit with AI channel. No violations.

## 1. Architecture
```
UI ─POST /ai/conversations/{id}/messages (SSE)─▶ Orchestrator.run_turn
        ├ ContextBuilder(window, system prompt, page context, LocaleContext/ResponseLanguage)
        ├ ToolCatalog.for(principal)  = registry ∩ authorize(permission) ∩ !disabled ∩ !ai_forbidden  (+ ExternalToolSource allow-list)
        ├ LLMProvider.chat(stream) ⇄ tool calls ─▶ ToolExecutor
        │      ├ re-authorize(principal, tool.permission, resource)   ✗ ⇒ ToolResult(error ai.tool_forbidden)
        │      ├ read/write ⇒ handler(AI principal) ⇒ ToolResult(sources, state)
        │      └ sensitive ⇒ PendingAction(params_hash, tool summary) ⇒ SSE pending_action  (no execution)
        ├ SourceAttributor (validate [n] markers vs collected sources, classes, caveats)
        └ Guardrails (tool/loop budgets, secret redaction, sanitized rendering)
User ─POST /ai/actions/{id}/confirm─▶ ConfirmationService token ─▶ domain service (AI-channel principal) ─▶ events/audit (actor_kind=ai, acting_for=user)
SearchAssistant(008) · DiagnosisFlow(016) · EmbeddingProvider(008) are thin facades over run_turn with restricted tool policies
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `ToolRegistry` / `ToolCatalog` | register, filter per principal, schema validate | authz | `register_ai_tool`, `for_principal` | permission filter + re-check | filtering tests |
| `ToolExecutor` | validate params, authorize, run/queue, redact | authz, domains | internal | no execution of sensitive inline | execution tests |
| `PendingActionService` | create/confirm/decline/expire, params hash, idempotent execute | `ConfirmationService`, jobs | API | owner session only; expiry ⇒ no run | confirmation tests |
| `Orchestrator` | turn loop, budgets, streaming events | provider, tools | `run_turn` | bounded loops; failure ⇒ error event | scripted-LLM tests |
| `ContextBuilder` | system prompt, window/token budget, untrusted-data framing, language | 026 | internal | tool results framed as data | prompt-structure tests |
| `SourceAttributor` | validate citations, classes, caveats | tool results | internal | invalid markers dropped | attribution tests |
| `LLMProvider` + OpenAI-compatible adapter | chat/stream/tools | `ConnectorHttpClient`-style client, `core.secrets` | Protocol + kit | timeouts, size caps, no secret logging | conformance kit |
| `ExternalToolSource` (MCP) | MCParr/MCP tools behind allow-list | `mcp` SDK, secrets | Protocol | default-deny, portal auth before call | allow-list tests |
| `ConversationService` | CRUD, retention, deletion | `core.db` | API | owner-only | privacy tests |
| `UsageGovernor` | rate limit, token budget, concurrency, kill switch | 021 limiter | internal | fail closed on budget | limit tests |
| Facades | `SearchAssistant`, `DiagnosisFlow`, `EmbeddingProvider` | orchestrator | ports | restricted tool policies | contract tests |
| Frontend | panel, cards, source chips, admin config | 022/004 | components | a11y; honest labelling | a11y/e2e |

## 3. Data Model — `data-model.md` · 4. Contracts — `contracts/ai-contracts.md`

## 5. Events
Produced: `ai.conversation_started`, `ai.action_confirmed|declined|expired`, `ai.provider_failed` (no content). AI-performed domain actions are emitted by owners with `actor_kind=ai`, `acting_for=<user>` (identical events/rules as human actions). Consumed: `plugin.state_changed` (tool registration), `admin.config_changed` (provider/limits), erasure participant. Idempotency: pending action execution keyed by `pending_action_id`.

## 6. Permissions & Security
`ai.use` (default grant to authenticated while `ai.enabled`), `ai.manage` (Admin; configuration/provider/MCP allow-list — **ai_forbidden as a tool**). Tool permissions are the domain permissions; sensitive actions use `ConfirmationService` + step-up when 003 requires; AI-forbidden list per R3. Provider API key and MCP credentials only in `core.secrets`; never in prompts, tool results, logs, events or audit. Rendering via the sanitized Markdown pipeline. Existence-leak: unauthorized tool/data requests return the same "not available" outcome as nonexistent items (per 003 policy).

## 7. Configuration — `data-model.md` settings (declared into 020).

## 8. External Integrations
LLM provider endpoint (operator-chosen; hosted or local) and optional MCP servers (MCParr). Both optional; portal fully functional without them.

## 9. Error Handling & Resilience
Provider down/timeouts ⇒ `ai.unavailable` event + panel state; classic features unaffected · mid-task error ⇒ no partial sensitive action (sensitive runs only after confirmation, atomically in the domain service) · tool failure ⇒ `ToolResult(error)` fed back, loop continues within budget · budget exhausted ⇒ polite stop · MCP server down ⇒ its tools omitted · SSE disconnect ⇒ turn cancelled, pending actions remain valid until TTL · confirmation after expiry ⇒ `ai.action_expired`.

## 10. Observability
Provider latency/error rate, tokens, tool-call counts by tool/outcome, refusals, pending-action funnel (created/confirmed/expired), injection-guard trips; registers `ai` with 025 (functional: probe completion within threshold; technical axis separate); no content in telemetry.

## 11. Testing Strategy
Scripted fake `LLMProvider` (deterministic tool-call scripts). Unit: tool filtering by principal; schema validation; citation validation; budget/loop limits; redaction. Integration (real PG): permission re-check when the model calls a forbidden tool; confirmation lifecycle (confirm/decline/expire/idempotent; params-hash tamper ⇒ refused); AI actions emit the same events/audit as human ones with `actor_kind=ai`; owner-only conversations/erasure; MCP allow-list default-deny with a fake MCP server. **Injection corpus** (documents/tickets/news with instructions to exfiltrate, escalate, call destructive tools) ⇒ no unauthorized data/execution. Contract: `SearchAssistant`, `DiagnosisFlow` (draft only, never submit), provider conformance kit. Frontend: streaming states, confirmation card accessibility, honest labelling of interpretation vs sources. E2E: ask → cited answer; sensitive action confirm/expire.

## 12. Migration / Versioning
Alembic revision for `ai`; tool schemas versioned (`name@version`), additive; provider adapters behind Protocol; conversation retention job; contract semver'd.

## 13. Cross-Spec Dependencies
Prerequisites: 001, 002/003 (principal channel, `ConfirmationService`, audit `actor_kind=ai`), 004 (AiEntry slot), 007, 020 (settings/secrets), 021 (limiter/retention), 022, 026 (response language). Implements ports for 008 and 016. Consumes tool registrations from 006, 008, 011, 016, 017, 024 (+ later 012, 013, 014, 015, 019). Optional: MCParr (external).

## 14. Implementation Phases
1 SDK, schema, provider port + OpenAI-compatible adapter + conformance → 2 Tool registry/catalog/executor with permission re-checks → 3 Orchestrator + SSE chat + conversations → 4 Source attribution + guardrails/injection corpus → 5 Pending actions/confirmation → 6 Usage governor + admin config → 7 Facades (SearchAssistant, DiagnosisFlow, EmbeddingProvider) → 8 Baseline tools for existing modules → 9 MCP/MCParr adapter → 10 Frontend polish, observability, hardening.

## 15. Technical Decisions — `research.md` R1–R14.

## 16. Risks / Open Technical Questions
- **R1** OQ-85..89 use plan defaults (research); **product confirmation requested** (sensitive/forbidden catalog, MCParr trust/mapping, citation granularity, audit detail).
- **R2** Prompt injection can never be fully eliminated at the model level; the design makes it non-exploitable for authorization/confirmation, but model-influenced *content* of answers remains probabilistic (documented, labelled interpretation).
- **R3** Model/tool-calling quality varies by provider; the conformance kit covers protocol behaviour, not answer quality.
- **R4** Token accounting is approximate for providers without usage reporting (conservative estimator).
- **R5** MCParr tool mapping needs an Admin workflow and per-tool permission decisions; default-deny keeps it safe.
- **R6** Long-term memory/personalization intentionally out of scope (privacy).

## Project Structure
```text
backend/src/portalab/{capabilities/ai, modules/ai/{tools,executor,pending,orchestrator,context,attribution,providers,external,conversations,governor,facades,admin,api,models}} · backend/migrations/ai/versions/
frontend/src/features/ai/{panel,confirmation,sources,admin}
```
