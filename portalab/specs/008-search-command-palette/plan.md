# Implementation Plan: Global Search & Command Palette

**Branch**: `008-search-command-palette` | **Date**: 2026-10-01 | **Spec**: `specs/008-search-command-palette/spec.md`
**Roadmap**: Phase 3 step 11 *Global Search*. Builds on 004 (palette/shell slots), 026 (language/locale), 003 (authorize, ConfirmationService), 022 (design system).

## Summary
A **federated, permission-at-source** search: domain modules register `SearchProvider`s (lexical via PostgreSQL FTS/trigram, optional semantic via pgvector and an optional `EmbeddingProvider`), a coordinator fans out in parallel with time budgets and returns grouped results with per-group functional states. The AI analysis runs as a **separate, independent SSE stream** through a `SearchAssistant` port (implemented by 018). Search history is private personal data. The Command Palette extends the 004 palette with an action catalog (sensitivity levels), object resolution, deterministic intents and AI-suggested (never auto-executed) interpretations. Domains' data, the AI engine and authorization remain with their owners.

## Technical Context
**Language**: Python 3.12 + TypeScript/React · **Deps (new)**: PostgreSQL extensions `unaccent`, `pg_trgm`, optional `vector` (pgvector); no new Python library required (asyncpg/SQLAlchemy) · **Storage**: schema `search` (history, embeddings, index_state) · **Testing**: pytest real PG (FTS configs, pgvector marked optional), Vitest, Playwright · **Constraints**: no result outside the principal's rights (CD-002, CD-016), classic results never wait for AI, AI optional (CD-021), PostgreSQL-only · **Scale**: personal/community (≤ 10⁶ documents total).

## Constitution Check — PASS
XVI/XVII Search ∥ AI independence · VI permission/privacy at source, history private (VII) · IX provider isolation and degraded states · XX no second authz/AI/event engine · III provider/action contributions for plugins · XII accessible palette/results. No violations.

## 1. Architecture
```
Browser ─POST /search──▶ SearchCoordinator ─┬▶ ParsedQuery(q, filters, language, tz via 026)
   │                                        ├▶ providers[kind] (parallel, timeout, cap) ─▶ own tables + FTS/trgm (+ embeddings → hydrate+authorize)
   │                                        └▶ merge by kind ─▶ groups{state, items, facets}
   └─POST /search/assist (SSE)─▶ SearchAssistant port (018)  [independent failure domain]
Palette: /palette/resolve ─▶ IntentResolver(deterministic) ─▶ ActionCatalog ∩ authorize ∩ page context ─▶ ObjectResolver
         unresolved ─▶ SearchAssistant.interpret() ⇒ suggestions only
Indexing (semantic only): provider Indexable ─▶ outbox job ─▶ EmbeddingProvider ─▶ search.embeddings
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `SearchCoordinator` | parse, fan out, timeouts, merge, group states, pagination | provider registry, 026 | `search()` | per-provider isolation; caps; never raises to caller | isolation/timeout tests |
| `QueryParser` | text, filters, mode, relative dates with `LocaleContext`, length/syntax safety | 026 | `parse()` | `websearch_to_tsquery`, parameterized only | parser tests incl. injection |
| Provider SDK + conformance kit | `SearchProvider` protocol, FTS helpers (tsvector column + GIN builders, snippet/highlight, unaccent/trgm) | PostgreSQL | helpers | provider must scope by principal inside query | conformance suite |
| Semantic index | embeddings table, outbox indexing job, ANN query, hydrate | `EmbeddingProvider`, jobs | `semantic_candidates()` | ids only; owner re-authorizes; over-fetch + iterate | recall/permission tests |
| `AssistGateway` | SSE bridge to `SearchAssistant`, event typing (`source_ref` vs `synthesis`) | 018 port | `/search/assist` | permission-bounded; failure isolated | failure tests |
| `HistoryService` | record/list/clear, caps, opt-out | `core.db` | API | owner-only access path | privacy tests |
| `ActionCatalog` / `IntentResolver` / `ObjectResolver` | palette backend | 004 contributions, 003 | `/palette/resolve` | permitted entries only; sensitivity flag | intent/permission tests |
| Frontend `SearchPage` + palette provider + `useSearchAssist` | grouped UI, filters, SSE, states | 022, 004 | components | each group has functional state; analysis visually distinct; keyboard accessible | component + e2e |
| Admin | reindex/status, settings | 020, 025 | `/admin/search/*` | `search.manage` audited | API tests |

## 3. Data Model — `data-model.md` · 4. Contracts — `contracts/search-contracts.md`

## 5. Events
Produced `search.performed` (counts only), `search.provider_failed` (deduped per provider/min); consumed none generically — providers trigger indexing from their own domain changes via the outbox. Consumers of `search.performed` (statistics 017, gamification 013) idempotent on `(user_id, request_id)`. No query text in events (FR-030).

## 6. Permissions & Security
| Operation | Permission | Notes |
|---|---|---|
| search / suggest | `search.use` (default grant) + each provider's `required_permission` and domain visibility rules | ungranted kinds omitted entirely |
| AI analysis | AI permission (018) | runs with principal rights (CD-003) |
| own history | `users.self.manage` | no cross-user path |
| palette sensitive action | owner module permission + `ConfirmationService` token | audited by owner |
| reindex / semantic settings | `search.manage` | audited |
Controls: rate limit per user, query length cap, escaped snippets, parameterized SQL, visibility re-check on hydrate, no existence leak through counts (counts only for permitted items).

## 7. Configuration — `data-model.md` settings (declared into 020).

## 8. External Integrations
None by default. `EmbeddingProvider` may later be a local model or the AI capability; never required.

## 9. Error Handling & Resilience
Provider timeout/error ⇒ group `unavailable`/`partial`, others unaffected, `search.provider_failed` · AI unavailable ⇒ analysis area `unavailable`, classic unaffected · classic failure ⇒ AI still answers from its permitted sources (FR-003) · pgvector/embedding absent ⇒ semantic `unavailable` banner, lexical continues · index lag ⇒ results re-hydrated, deleted/forbidden ids dropped · rate-limited ⇒ 429 problem+json · invalid filter ⇒ 422 with field detail · no results ⇒ explicit empty state with next action.

## 10. Observability
Metrics: latency per provider/overall, timeouts, zero-result rate, semantic availability, index lag, AI stream failures. Registers `search` component with 025 (functional: representative probe search per provider returns without error).

## 11. Testing Strategy
Unit: parser/relative dates (user tz/first-day), facet validation, merge/grouping. Provider conformance suite (every provider must pass: permission scoping, visibility change effective on next query, timeout behavior). Integration (real PG): FTS ranking/unaccent/trigram; pgvector candidate → hydrate → authorize drops forbidden; history cap/retention/clear/opt-out and cross-user isolation; AI failure vs search failure independence; rate limiting. Security: no leakage via counts/snippets/facets, injection attempts, history privacy. Frontend: grouped states, filter updates without reset, SSE distinction between sources and synthesis, palette context actions, confirmation on sensitive actions. E2E: keyboard-only search and palette.

## 12. Migration / Versioning
Alembic revision for `search` (extensions created idempotently; pgvector optional and detected — migration succeeds without it, semantic disabled); embedding table rebuildable; provider/action contracts semver'd.

## 13. Cross-Spec Dependencies
Prerequisites: 001 kernel (jobs/outbox, capability registry), 003 (`authorize`, `ConfirmationService`), 004 (palette registry, slots), 022 (states), 026 (LocaleContext, `normalize_for_search`), 020 (settings), 021 (rate limit, retention). Exposes: `SearchProvider`/`ActionDef` SDK to every domain spec (010 inbox, 011, 012, 015, 016, 024, …), `search.performed` to 013/017. Consumes later: 018 (`SearchAssistant`, optional `EmbeddingProvider`). Until 018: assistant slots show "not available".

## 14. Implementation Phases
1 SDK + coordinator + query parser → 2 First providers (navigation destinations, users directory, services) + conformance kit → 3 REST API + frontend grouped UI/filters → 4 History → 5 Palette backend (actions/objects/intents) + sensitive-action flow → 6 Assist gateway (SSE, port stub) → 7 Semantic index (optional) → 8 Admin/observability/hardening. Domain providers (Media, Wiki, News, Tickets, Community, Calendar, Marketplace, Statistics, Gamification) are delivered by each owning spec's tasks using the SDK.

## 15. Technical Decisions — `research.md` R1–R14.

## 16. Risks / Open Technical Questions
- **R1** pgvector availability in the target PostgreSQL image: ship image with the extension; migration tolerates absence. Semantic is therefore **conditional**, honestly surfaced (FR-023).
- **R2** ANN post-filtering recall under permission scoping: over-fetch factor + iterative widening; measured in tests; acceptable at personal scale.
- **R3** Federated fan-out latency grows with providers: per-provider budget + parallelism + result caps; revisit with a central lexical index only if measurements demand (ADR then).
- **R4** Open product questions OQ-35..39 use defaults (research R14). **Product confirmation requested** (AI scope, history retention, action catalog/sensitive set).
- **R5** Domain providers depend on specs implemented later; coverage of FR-012 is complete only when all domains ship — tasks provide the conformance kit and a provider template.

## Project Structure
```text
backend/src/portalab/{capabilities/search, modules/search/{coordinator,parser,semantic,assist,history,palette,api,models}} · backend/migrations/search/versions/
frontend/src/features/search/{SearchPage,groups,filters,assist,history} · frontend/src/shell/palette/providers/search.ts
```
