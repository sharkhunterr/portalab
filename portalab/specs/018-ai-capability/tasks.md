---
description: "Task list — AI Capability (spec 018)"
---

# Tasks: AI Capability

**Input**: `specs/018-ai-capability/` · **Branch**: `018-ai-capability` · **Roadmap**: Phase 5 step 18 · **Tests**: included.
Abbrev: **`AI/`** = `backend/src/portalab/modules/ai`, **`CAP/`** = `backend/src/portalab/capabilities/ai`, **`FA/`** = `frontend/src/features/ai`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` kernel/jobs/secrets · `D-002/003` principal (`channel=ai`), `authorize`, `ConfirmationService`, `AuditSink` (`actor_kind=ai`, `acting_for`) · `D-004` `AiEntry` slot · `D-007` events · `D-020` settings · `D-021` rate limiter/retention · `D-022` UI · `D-026` `ResponseLanguage` · `D-008` ports `SearchAssistant`/`EmbeddingProvider` · `D-016` `DiagnosisFlow`. Domain tools (media 024, wiki/news/calendar 011, tickets 016, statistics 017, health 006, search 008, navigation 004) are registered by their owners using this SDK; this plan ships baseline wrappers for modules that already exist in the plan chain.

## Phase 1: Setup
- [X] T001 Create `CAP/__init__.py`, `AI/{tools,executor,pending,orchestrator,context,attribution,providers,external,conversations,governor,facades,admin,api,models}/__init__.py`, `backend/migrations/ai/versions/`, `FA/{panel,confirmation,sources,admin}/`, `backend/tests/{unit,integration,contract,security}/ai/`, `backend/tests/data/injection_corpus/`, `frontend/tests/{unit,e2e}/ai/`
- [X] T002 [P] Add deps (`jsonschema`; optional extra `mcp`) and declare settings (`ai.enabled`, `ai.provider.kind|endpoint|model` + secret `ai.provider.apiKey`, `ai.maxToolCallsPerTurn`, `ai.maxContextTokens`, `ai.requestTimeoutSeconds`, `ai.dailyTokenBudgetPerUser`, `ai.rateLimitPerMinute`, `ai.retentionDays`, `ai.pendingActionTtlMinutes`, `ai.autoNavigate`, `ai.tools.disabled`, `ai.mcp.servers`) in `AI/settings.py`; permissions `ai.use` (default grant while enabled), `ai.manage` (audited, `ai_forbidden`) in `AI/permissions.py`
- [X] T003 [P] Register retention target, classify conversations/messages as `content` personal data, implement 020/021 export+erasure participant `AI/privacy.py` (owner-only; excluded from admin views)

## Phase 2: Foundational — contracts, schema, provider port
### Tests first
- [X] T004 [P] Write `backend/tests/contract/ai/test_provider_kit.py`: `LLMProvider` conformance kit (streaming chunks, tool-call round trip, timeout, size caps, error mapping, no secret in logs) run against a fake server and the OpenAI-compatible adapter
- [X] T005 [P] Write `backend/tests/integration/ai/test_schema.py`: tables/constraints, `(conversation_id, seq)` unique, pending action states, FKs only intra-module/`identity.users(id)`
### Implementation
- [X] T006 Implement `CAP/` contracts (`AITool`, `ToolResult`, `SourceRef`, `LLMProvider`, `ExternalToolSource`, `AIEvent`) and `AI/models` + Alembic revision for schema `ai`
- [X] T007 Implement `AI/providers/openai_compat.py` (Chat Completions + tool calling + SSE streaming via safe HTTP client, secrets from `core.secrets`, redacted logging) and a scripted `FakeProvider` for tests

## Phase 3: US1 — AI reachable everywhere, under the user's permissions (P1) 🎯 MVP
**Independent test**: a user chats from any page; the AI offers/uses only what that user may access.
- [X] T008 [P] [US1] Write `backend/tests/integration/ai/test_permission_bounds.py`: tool catalog for a principal contains only permitted tools; a model-hallucinated call to an unpermitted tool is refused at execution (`ai.tool_forbidden`); AI principal never widens rights (Admin vs user); unpermitted data/existence not revealed; AI disabled/unavailable ⇒ `/ai/status` unavailable and classic API unaffected
- [X] T009 [US1] Implement `AI/tools/registry.py` (`register_ai_tool`, schema validation, `for_principal` filtering by `authorize` + disabled list + `ai_forbidden`) and `AI/executor/executor.py` (param validation, re-authorization, redaction, state mapping)
- [X] T010 [US1] Implement `AI/orchestrator/orchestrator.py` (turn loop, provider streaming, tool-call budget/loop limits, SSE `AIEvent`s) and `AI/context/builder.py` (system prompt, sliding window/token budget, untrusted-data framing, `ResponseLanguage`)
- [X] T011 [US1] Implement `AI/conversations/service.py`, routers `GET /ai/status`, `POST/GET/DELETE /ai/conversations`, `POST /ai/conversations/{id}/messages` (SSE) and `GET /ai/tools` in `AI/api/router.py`
- [X] T012 [US1] Implement frontend `FA/panel/AiPanel.tsx` (conversation, streaming, unavailable state, keyboard accessible) wired into the 004 `AiEntry` slot

## Phase 4: US8 — Resilience: AI failure never breaks classic functions (P1)
- [X] T013 [P] [US8] Write `backend/tests/integration/ai/test_resilience.py`: provider down/timeout ⇒ `ai.unavailable` only on AI routes; search/navigation/tickets unaffected; mid-turn provider error leaves no sensitive action executed; SSE disconnect cancels turn; budget/rate exhaustion handled politely
- [X] T014 [US8] Implement `AI/governor/governor.py` (per-user rate limit, daily token budget via `ai.usage_daily`, concurrency cap, kill switch, fail-closed on budget) and error/timeout mapping in the orchestrator

## Phase 5: US5 — Act: authorized actions with confirmation for sensitive ones (P1)
- [X] T015 [P] [US5] Write `backend/tests/integration/ai/test_pending_actions.py`: sensitive tool call creates a pending action (no execution) with tool-generated summary; confirm in time executes once via `ConfirmationService` (idempotent, step-up where required); decline/expiry ⇒ no execution; params-hash tamper refused; confirm only from owner's own session (AI cannot confirm); AI-forbidden tools unavailable even to Admin
- [X] T016 [P] [US5] Write `backend/tests/integration/ai/test_action_parity.py`: a write tool (e.g. create ticket draft) and a confirmed sensitive action run the same domain service path as the human API, emit the same events with `actor_kind=ai`/`acting_for`, and are audited identically (sensitive ones with redacted params + hash, conversation/message ids, no prompt text)
- [X] T017 [US5] Implement `AI/pending/service.py` (create/confirm/decline/expire job, params hash, idempotent execute), routers `GET /ai/actions/{id}`, `POST …/confirm|decline`, and `FA/confirmation/ConfirmationCard.tsx` (tool summary, expiry countdown, focus management)
- [X] T018 [US5] Document/implement the sensitivity catalog (`docs/ai-sensitive-actions.md`; tool flags validated at registration against 003's sensitive permission registry; `ai_forbidden`: admin transfer, secrets/credentials, AI config, audit/event mutation)

## Phase 6: US2 — Understand, search, synthesize with source attribution (P1)
- [X] T019 [P] [US2] Write `backend/tests/unit/ai/test_attribution.py`: `[n]` markers validated against sources retrieved in the turn (invalid dropped); source classes `real|historical|knowledge` with `as_of`; partial/stale/unavailable tool results produce caveats; no invented source ever shown
- [X] T020 [P] [US2] Write `frontend/tests/unit/ai/sources.test.tsx`: per-answer sources list + inline chips; uncited prose labelled as interpretation; caveat banner; accessible (text labels, not color-only)
- [X] T021 [US2] Implement `AI/attribution/attributor.py` and baseline read tools (`AI/tools/baseline/{search,wiki,statistics,health,navigation}.py`) wrapping the existing 008/011/017/006/004 service functions with proper permissions; `FA/sources/SourceList.tsx`

## Phase 7: US6 + US3 + US4 — Domain access, navigation, advice (P1/P2)
- [X] T022 [P] [US6] Write `backend/tests/security/ai/test_injection_corpus.py`: corpus in `backend/tests/data/injection_corpus/` (wiki/news/ticket/comment/service-name payloads instructing exfiltration, escalation, destructive tool calls, markup/exfil links) ⇒ no unauthorized data, no sensitive execution without confirmation, no secrets in output, model output rendered sanitized (external images blocked)
- [X] T023 [P] [US6] Write `backend/tests/security/ai/test_history_privacy.py`: AI access to history/statistics honors "historized ≠ public"; cannot read another user's conversations or personal history; aggregation never de-anonymizes (017 cohort rules apply through tools)
- [X] T024 [P] [US3] Write `backend/tests/integration/ai/test_navigation.py`: `navigate.suggest` returns only routes present in the user's 004 navigation view; unpermitted destinations omitted without leak; UI renders buttons (no auto-navigation unless `ai.autoNavigate`)
- [X] T025 [US3] Implement `navigate.suggest` tool + `FA/panel/NavigationSuggestion.tsx`, and explain-this-page support through page context (`context` on conversation, help pages via 011 `HelpResolver`)
- [X] T026 [US4] Implement advise/diagnose/recommend behaviors via prompt policy + read tools only (grounded in permitted data), with labelled interpretation; tests `backend/tests/integration/ai/test_advice_grounding.py` (no answer presents unverified data as real)

## Phase 8: Ports for other specs
- [X] T027 [P] Write `backend/tests/contract/ai/test_facades.py`: `SearchAssistant.stream/interpret` (read-only tool policy, result refs bounded to principal, interpret returns schema-validated suggestions only), `DiagnosisFlow` executor (fixed read-only subset, produces a ticket draft only, never submits, AI failure ⇒ error result), optional `EmbeddingProvider`
- [X] T028 Implement `AI/facades/{search_assistant,diagnosis,embeddings}.py` registered in the capability registry for 008/016

## Phase 9: US7 — MCParr as optional access/action layer (P2)
- [X] T029 [P] [US7] Write `backend/tests/integration/ai/test_mcp_source.py` (fake MCP server): only allow-listed tools exposed with mapped permission/sensitivity; unmapped tools invisible; portal authorization checked before every call; sensitive MCP tool requires confirmation; MCParr down ⇒ tools omitted, AI continues; credentials only from `core.secrets`, never to the model
- [X] T030 [US7] Implement `AI/external/mcp.py` (`ExternalToolSource` via `mcp` SDK HTTP transports), admin routers `GET/PUT /admin/ai/mcp-servers` (allow-list mapping UI `FA/admin/McpAllowlist.tsx`, audited, secrets masked)

## Phase 10: Polish & cross-cutting
- [X] T031 [P] Implement admin `PUT /admin/ai/config`, `POST /admin/ai/provider/test`, `GET /admin/ai/usage` (metrics only, no content) and `FA/admin/AiSettings.tsx`; ensure `ai.manage` routes are `ai_forbidden` as tools
- [X] T032 [P] Register `ai` with Observability (provider latency/errors, tokens, tool-call outcomes, pending-action funnel, guard trips; technical vs functional axes) in `AI/observability.py`; emit `ai.*` events (no content)
- [X] T033 [P] Write `backend/tests/security/ai/test_secrets_audit.py`: no secrets/API keys/MCP credentials in prompts, tool results, logs, events, audit or responses; audit entries contain ids/hashes not prompts; conversations excluded from admin views and exports to others
- [X] T034 [P] Add `/ai/*`, `/admin/ai/*` to the permission-matrix test, regenerate OpenAPI client, write `docs/ai.md` (tool authoring guide, sensitivity classes, provider adapters, MCP allow-list, injection model)

## Cross-spec obligations (audit 2026-10-01 — see `decisions/PLAN_FOLLOWUPS.md`)
- [X] T035 Provide the read-only `ai.invoke` facade for 019 (text drafting/classification into text fields, read-only tool policy, never usable as a condition or in sensitive params) in `AI/facades/automation.py`; test `backend/tests/contract/ai/test_ai_invoke.py` (F12)
- [X] T036 [P] Expose owner-tagged registration on the AI tool registry: `register(..., owner="module:<id>|plugin:<key>")` and `unregister(owner)`, with a test in `backend/tests/unit/ai/test_registry_owner.py` proving all contributions of an owner disappear (required by 023's conformance sweep, F20)

- [X] T037 Run `specs/018-ai-capability/quickstart.md` end-to-end; record deviations and open product confirmations (OQ-85..89 defaults)

## Dependencies & Order
Setup → Foundational → US1 (MVP) → US8 → US5 → US2 → US6/US3/US4 → ports/facades → US7 → Polish. US5 depends on the executor and `ConfirmationService`; facades need the orchestrator and tool policies; injection corpus (T022) must pass before any write tool from other specs is registered.
**Parallel examples**: T004/T005 · T008 with T013 · T015/T016 · T019/T020 · T022/T023/T024 · T031–T034.
**MVP**: Phases 1–3 (provider port + adapter, permission-filtered tools, orchestrator with SSE chat and conversations).

## Format validation
37 tasks, all checkbox + ID + path; story labels only on story phases.
