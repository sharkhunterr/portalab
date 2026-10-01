---
description: "Task list — Global Search & Command Palette (spec 008)"
---

# Tasks: Global Search & Command Palette

**Input**: `specs/008-search-command-palette/` · **Branch**: `008-search-command-palette` · **Roadmap**: Phase 3 step 11 · **Tests**: included.
Abbrev: **`SR/`** = `backend/src/portalab/modules/search`, **`CAP/`** = `backend/src/portalab/capabilities/search`, **`FS/`** = `frontend/src/features/search`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` jobs/outbox + capability registry · `D-003` `authorize` + `ConfirmationService` · `D-004` palette registry/slots · `D-022` `FunctionalState` · `D-026` `LocaleContext` + `normalize_for_search` · `D-020` settings · `D-021` rate limiter/retention · `D-007` events · `D-025` health. `SearchAssistant`/`EmbeddingProvider` implementations arrive with 018 (stubs here). Domain providers (Media, Wiki, News, Tickets, Community, Calendar, Marketplace, Statistics, Gamification) are delivered by their owning specs using this SDK.

## Phase 1: Setup
- [ ] T001 Create `CAP/__init__.py`, `SR/{coordinator,parser,semantic,assist,history,palette,api,models}/__init__.py`, `backend/migrations/search/versions/`, `FS/{groups,filters,assist,history}/`, `backend/tests/{unit,integration,contract,security}/search/`, `frontend/tests/{unit,e2e}/search/`
- [ ] T002 [P] Declare settings (`search.providerTimeoutMs`, `.maxResultsPerGroup`, `.maxQueryLength`, `.historyRetentionDays`, `.historyMaxEntries`, `.semantic.enabled|embeddingProvider|topK`, user `search.historyEnabled`) in `SR/settings.py`; permissions `search.use` (default grant to authenticated), `search.manage` (audited) in `SR/permissions.py`
- [ ] T003 [P] Register retention target for `search.history` (021) and classify `query_text` as `activity` personal data in the PII registry

## Phase 2: Foundational — SDK, schema, coordinator
### Tests first
- [ ] T004 [P] Write `backend/tests/unit/search/test_parser.py`: filters/mode extraction; length cap; syntax-safe handling of quotes/operators/SQL metacharacters; relative dates ("this week", "recently") resolved with user tz and first-day-of-week from `LocaleContext`
- [ ] T005 [P] Write `backend/tests/unit/search/test_coordinator.py`: parallel fan-out; per-provider timeout ⇒ group `unavailable`; provider exception isolated; group order stable; caps enforced; ungranted kinds absent
- [ ] T006 [P] Write `backend/tests/contract/search/test_provider_conformance.py`: reusable conformance kit — provider scopes by principal inside the query, visibility change effective on next query, timeout/cancel respected, snippets escaped
### Implementation
- [ ] T007 Implement `CAP/` contracts (`SearchProvider`, `SearchItem`, `ParsedQuery`, `FacetDef`, `EmbeddingProvider`, `SearchAssistant`, `ActionDef`, `ObjectResolver`) and the registry (`register_provider`)
- [ ] T008 Implement `SR/models` + Alembic revision for schema `search` (extensions `unaccent`, `pg_trgm`; pgvector optional/detected; history, index_state, embeddings when available)
- [ ] T009 Implement `SR/parser/parser.py` (`QueryParser`) per T004
- [ ] T010 Implement `SR/coordinator/coordinator.py` (parallel fan-out with budgets, merge, grouping, pagination cursors) per T005
- [ ] T011 [P] Implement provider helper kit `CAP/fts.py` (tsvector generated-column + GIN migration helper, `websearch_to_tsquery` builder, unaccent/trigram ranking, highlight/snippet with escaping, language→FTS config mapping)

## Phase 3: US1 + US3 — Classic search, exact/semantic, filters, grouping (P1) 🎯 MVP
**Independent test**: query returns grouped, filtered results immediately with no dependency on the AI.
- [ ] T012 [P] [US1] Write `backend/tests/integration/search/test_search_api.py`: `POST /search` returns groups with per-group state and facets without invoking AI; applying/removing a filter changes results; cursor pagination; typo/accents matched; rate limit 429
- [ ] T013 [P] [US3] Write `backend/tests/integration/search/test_semantic.py` (marked requires pgvector): meaning-related match without exact terms; candidates re-hydrated and re-authorized (forbidden dropped); stale/deleted ids dropped; absence of `EmbeddingProvider` ⇒ semantic reported `unavailable` honestly while lexical works
- [ ] T014 [US1] Implement routers `POST /search`, `GET /search/suggest` in `SR/api/router.py` with rate limiting and problem codes
- [ ] T015 [US3] Implement first providers via the SDK: navigation destinations (from 004 manifest), users directory (visibility via 021 `VisibilityFilter`), services (006) in `SR/providers/`
- [ ] T016 [US3] Implement semantic index: `SR/semantic/indexer.py` (outbox job from provider `Indexable`, content-hash skip), `SR/semantic/query.py` (ANN top-K over-fetch + iterative widening → `hydrate`), tolerant of missing pgvector
- [ ] T017 [US1] Implement frontend `FS/SearchPage.tsx`, `groups/ResultGroup.tsx` (per-group `FunctionalState`), `filters/FilterBar.tsx`, TanStack Query hooks, empty state with next action (FR-022)

## Phase 4: US2 — Resilience: classic and AI fail independently (P1)
- [ ] T018 [P] [US2] Write `backend/tests/integration/search/test_assist_independence.py`: AI down ⇒ `/search` unaffected; classic failure ⇒ assist still streams from permitted sources; event types `source_ref` vs `synthesis` distinguishable; stream aborts cleanly on disconnect
- [ ] T019 [US2] Implement `SR/assist/gateway.py` + `POST /search/assist` (SSE) bridging the `SearchAssistant` port (stub returning `unavailable` until 018), principal-bounded references only
- [ ] T020 [US2] Implement `FS/assist/useSearchAssist.ts` and `AssistPanel.tsx` (analysis visually distinct from results, source labels, independent unavailable/error states, retry)

## Phase 5: US4 — Permission- and privacy-bounded results (P1)
- [ ] T021 [P] [US4] Write `backend/tests/security/search/test_no_leak.py`: ungranted domain contributes nothing (not even counts/facets); private data of another user never returned by permission alone; permission/visibility change effective on next search; snippets never include restricted fields; AI refs limited to principal-visible items
- [ ] T022 [US4] Enforce provider visibility via authz/`VisibilityFilter` in the conformance kit and coordinator (kinds filtered by `required_permission`; counts only over permitted items); add audit-free metrics without query text

## Phase 6: US5 — Search across all listed domains (P2)
- [ ] T023 [P] [US5] Write `backend/tests/contract/search/test_domain_coverage.py`: checklist test enumerating expected kinds (media, wiki, news, tickets, community, calendar, marketplace, services, statistics, gamification) — passes for those registered, reports pending ones (xfail-with-reason until owning specs land)
- [ ] T024 [US5] Implement provider template + docs `docs/search-providers.md` and `SR/providers/_template.py` so each domain spec adds its provider with tests from the kit

## Phase 7: US6 — Search history (P3)
- [ ] T025 [P] [US6] Write `backend/tests/integration/search/test_history.py`: recorded as personal data, upsert dedup, cap and retention, clear one/all, opt-out via `search.historyEnabled`, never readable by another user, included in export and erased with account
- [ ] T026 [US6] Implement `SR/history/service.py`, routers `GET/DELETE /me/search-history[/{id}]`, retention job, and `FS/history/HistoryList.tsx`

## Phase 8: US7 — Command Palette: navigate, search, act, open objects (P1)
- [ ] T027 [P] [US7] Write `backend/tests/integration/search/test_palette_resolve.py`: only permitted destinations/actions returned; context actions depend on `route`; object ref (`#id`, `portalab://kind/id`) opens directly; sensitive action returns `confirmation_required`; unknown refs reveal nothing
- [ ] T028 [P] [US7] Write `frontend/tests/e2e/search/palette-search.spec.ts`: `Mod+K` on a ticket page shows context actions; search results inside palette; destructive action asks confirmation and is audited server-side; keyboard-only flow; focus restore
- [ ] T029 [US7] Implement `SR/palette/{catalog,objects,resolver}.py` and `GET /palette/resolve`; extend `NavigationContribution` handling (004) with `sensitivity` and `confirmation_required`
- [ ] T030 [US7] Implement frontend palette provider `frontend/src/shell/palette/providers/search.ts` (inline search results, object open, sensitive-action confirmation via `ConfirmationService` token flow)

## Phase 9: US8 — Natural-language queries (P2)
- [ ] T031 [P] [US8] Write `backend/tests/unit/search/test_intents.py`: deterministic intents per language (navigate/search/known commands/aliases) resolve instantly without AI; unresolved text produces AI suggestions only (never executed); AI outage ⇒ deterministic path unaffected; suggestions pass the same permission filter
- [ ] T032 [US8] Implement `SR/palette/intents.py` (grammar + alias tables from catalogs via 026) and `interpret()` bridge to the `SearchAssistant` port with parallel, non-blocking calls; frontend suggestion rendering labelled "suggested by assistant"

## Phase 10: Polish & cross-cutting
- [ ] T033 [P] Implement admin `POST /admin/search/reindex`, `GET /admin/search/status` (`search.manage`, audited) and Observability registration (probe search per provider, latency/timeout/zero-result/index-lag metrics) in `SR/observability.py`
- [ ] T034 [P] Emit `search.performed` (counts only, dedup `(user_id, request_id)`) and `search.provider_failed` via `EventPublisher`; add test that no query text reaches events or logs
- [ ] T035 [P] Add `/search*`, `/palette/*`, `/me/search-history*`, `/admin/search/*` to the permission-matrix test, regenerate OpenAPI client, wire provider conformance kit into CI `test` stage

## Cross-spec obligations (audit 2026-10-01 — see `decisions/PLAN_FOLLOWUPS.md`)
- [ ] T036 [P] Expose owner-tagged registration on the search provider and action registries: `register(..., owner="module:<id>|plugin:<key>")` and `unregister(owner)`, with a test in `backend/tests/unit/search/test_registry_owner.py` proving all contributions of an owner disappear (required by 023's conformance sweep, F20)

- [ ] T037 Run `specs/008-search-command-palette/quickstart.md` end-to-end; record deviations and open product confirmations (OQ-35..39 defaults)

## Dependencies & Order
Setup → Foundational → US1/US3 (MVP) → US2 → US4 → US7 → US5 → US6 → US8 → Polish. US4 hardening should land before any real domain provider ships; US7 depends on 004 palette; US8 depends on US7; US2 needs only the port stub.
**Parallel examples**: T004/T005/T006 · T012/T013 · T018 with T021 · T033/T034/T035.
**MVP**: Phases 1–3 (SDK, coordinator, lexical grouped search with filters, first providers, UI).

## Format validation
37 tasks, all checkbox + ID + path; story labels only on story phases.
