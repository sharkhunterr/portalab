---
description: "Task list — Media (spec 024)"
---

# Tasks: Media

**Input**: `specs/024-media/` · **Branch**: `024-media` · **Roadmap**: Phase 5 step 16 · **Tests**: included.
Abbrev: **`MD/`** = `backend/src/portalab/modules/media`, **`CAP/`** = `backend/src/portalab/capabilities/{media,media_core}`, **`FM/`** = `frontend/src/features/media`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` kernel/jobs/blobstore · `D-002/003` principal/authz · `D-005` connectors (RecordSink, capability mechanism, source-of-truth) · `D-006` health · `D-007` events · `D-008` search SDK · `D-009` widget registry · `D-010` category registry · `D-017` statistics packs · `D-020` settings · `D-021` visibility · `D-022/004` UI. Concrete connectors (Plex/Radarr/Sonarr/Seerr/Grimmory/RomM…) are separate deliverables validated by the conformance kits built here; quota units are credited by 015 through Media's own `RequestQuotaService` (CD-034).

## Phase 1: Setup
- [ ] T001 Create `CAP/media/__init__.py`, `CAP/media_core/__init__.py`, `MD/{types,sink,identity,fields,images,availability,playback,links,history,requests,discovery,sections,providers,api,models}/__init__.py`, `backend/migrations/media/versions/`, `FM/{home,catalog,detail,playback,requests,links,admin}/`, `backend/tests/{unit,integration,contract,security}/media/`, `frontend/tests/{unit,e2e}/media/`
- [ ] T002 [P] Declare settings (`media.fieldPriority.<kind>.<field>`, `media.finishedThreshold.<kind>`, `media.playback.pollActiveSeconds|pollIdleSeconds|staleTimeoutSeconds|progressEventSeconds`, `media.requests.quotaPerPeriod|period`, `media.match.autoThreshold`, `media.discovery.*`) in `MD/settings.py`; permissions `media.read` (default grant), `media.request` (default grant), `media.manage` (audited) in `MD/permissions.py`
- [ ] T003 [P] Register datum classes `media_history`, `media_request` (default Private) with the 021 visibility registry; classify history/progress/links/requests/sessions in the PII registry; implement 020/021 export+erasure participant `MD/privacy.py`; register retention targets

## Phase 2: Foundational — capabilities, schema, registries
### Tests first
- [ ] T004 [P] Write `backend/tests/contract/media/test_capability_kits.py`: conformance kits for `media.library`, `media.playback`, `request.service` with fake providers (typed results with `as_of`/provenance; error/timeout behavior)
- [ ] T005 [P] Write `backend/tests/integration/media/test_schema.py`: tables/constraints, unique `(scheme,value)`, unique `(service_id, external_id)`, `merge_log` append-only, FKs only intra-module or `identity.users(id)`
### Implementation
- [ ] T006 Implement `CAP/` capability Protocols, `SourceRecord` kinds, fake providers, `MediaCatalog`/`HistoryReader`/`ProgressReader`/`RecommendationProvider` protocols and the `RequestQuotaService` interface
- [ ] T007 Implement `MD/models` + Alembic revision for schema `media`
- [ ] T008 Implement `MD/types/registry.py` (`register_media_type`: movie, series, season, episode, book, game, album, track baseline; hierarchy and thresholds) and detail slot registry `register_detail_block`

## Phase 3: US1 + US2 — Unified catalog, service-independent identity, aggregation (P1) 🎯 MVP
**Independent test**: two fake sources provide the same film ⇒ one Media Object with merged, provenance-tracked fields; removing a source never removes the object.
- [ ] T009 [P] [US1] Write `backend/tests/integration/media/test_identity.py`: shared strong id ⇒ same object; fuzzy match ⇒ candidate only (no auto-merge); conflicting ids never merge; merge/split reversible and logged; source disappearance keeps object and history; hierarchy series→season→episode
- [ ] T010 [P] [US2] Write `backend/tests/integration/media/test_field_resolution.py`: per-field priority matrix; admin override beats sources; provenance recorded; priority change recomputes deterministically; no provider assumed mandatory (works with a single source and with none ⇒ empty catalog)
- [ ] T011 [P] [US2] Write `backend/tests/integration/media/test_library_sink.py`: idempotent upsert on `(service_id, external_id)`; `removed` ⇒ `active=false` only; sanitized payload (no secrets/URLs with credentials); duplicate delivery safe
- [ ] T012 [US1] Implement `MD/sink/library.py` (`RecordSink` for `media.library`) and `MD/identity/resolver.py` (id-first, candidates, admin merge/split with `merge_log`)
- [ ] T013 [US2] Implement `MD/fields/resolver.py` (candidates → effective + provenance, admin overrides) and recompute job; `MD/images/service.py` (fetch via connector client, validate/re-encode, blobstore, proxy endpoint)
- [ ] T014 [US1] Implement catalog API `GET /media`, `GET /media/{id}`, `GET /media/images/{id}` with visibility/permission bounds and cursor pagination; frontend `FM/catalog/CatalogPage.tsx` (grid/list, filters, states)
- [ ] T015 [US2] Implement admin matching/merge/override routers (`/admin/media/match-candidates`, `merge`, `split`, `objects/{id}/overrides`) with `ConfirmationService` + `AuditSink`, and `FM/admin/MatchingScreen.tsx`

## Phase 4: US10 — Availability vs service health vs sync (P1)
- [ ] T016 [P] [US10] Write `backend/tests/integration/media/test_availability.py`: object availability, `health.service_state` and last sync outcome returned separately; service outage or sync error does not remove or flip catalog entries; stale marked with `as_of`; media unavailable (no active source) distinct from service unavailable
- [ ] T017 [US10] Implement `MD/availability/service.py` composing 005/006 facts side by side and the `sources` section payload; frontend `FM/detail/SourcesSection.tsx` showing the three facts distinctly with non-color cues

## Phase 5: US3 — Extensible detail page (P1)
- [ ] T018 [P] [US3] Write `backend/tests/integration/media/test_detail_sections.py`: sections `info|sources|history|progress|requests|people|statistics` (017 provider) `|events` (associated domain events, 007 history) `|actions` (permitted actions incl. request/open, plugin actions) `|links` (external-service links without secrets) `|blocks` each return `{state, as_of, data}`; one failing source degrades only its section; personal sections respect visibility; "concerned users" list limited to users whose visibility allows
- [ ] T019 [P] [US3] Write `frontend/tests/unit/media/detail.test.tsx`: independent section frames and states; plugin block slot rendering (declarative template) with permission gating; failing block isolated
- [ ] T020 [US3] Implement `MD/sections/*.py` + `GET /media/{id}/sections/{name}`, slot registry exposure, and frontend `FM/detail/DetailPage.tsx` with per-section `FunctionalState` frames and block slots

## Phase 6: US4 — Source-agnostic playback / current activity (P1)
- [ ] T021 [P] [US4] Write `backend/tests/integration/media/test_playback.py`: sessions from two different fake sources normalized identically; state transitions emit throttled events with dedup `(session_key, state_seq)`; source outage ⇒ `stale` then `interrupted` after timeout with `media.playback_error`; session end ⇒ `media.playback_finished` (≥ threshold) or `media.playback_abandoned`; unlinked source activity not attributed; poll cadence adapts (active/idle)
- [ ] T022 [US4] Implement `MD/links/service.py` (+ `/me/media/links` endpoints, verification when supported) and `MD/playback/{poller,normalizer}.py` (jobs per service, advisory-lock-safe), session upserts and events via `EventPublisher`; frontend `FM/playback/NowPlaying.tsx`

## Phase 7: US5 — Media history feeding the backbone (P1)
- [ ] T023 [P] [US5] Write `backend/tests/integration/media/test_history.py`: event replay rebuilds `history_entries`/`user_progress` identically; finished thresholds per kind; `finished` sticky and emitted once; cross-source reconciliation by greatest `occurred_at`; out-of-order events; personal history Private by default and erased with account
- [ ] T024 [US5] Implement `MD/history/projection.py` (007 consumers, `idempotent_effect`), `media.playback_finished` (once per session, sticky progress) and `media.resume_available` emission, `GET /me/media/history|continue`, and `FM/home/ContinueShelf.tsx`; register event types with 007 (envelope shape per FR-040)

## Phase 8: US6 — Media requests (P2)
- [ ] T025 [P] [US6] Write `backend/tests/integration/media/test_requests.py`: submit via `request.service` fake; state mirror and normalization; reconciliation by source-of-truth; quota enforcement (base per period + extra units in `RequestQuotaService`, credited by a 015 stub; ledgered, idempotent); order never depends on purchased quota; idempotency key; cancel; events `media.request_*`
- [ ] T026 [US6] Implement `MD/requests/service.py`, `MD/requests/quota.py` (`RequestQuotaService`: base quota, extra-unit balance and ledger, `add_units/remove_units` for 015), `RecordSink` for request records, routers `POST /media/requests`, `GET /me/media/requests`, `POST …/cancel`, and `FM/requests/RequestFlow.tsx`

## Phase 9: US7 — Search & discovery via existing engines (P2)
- [ ] T027 [P] [US7] Write `backend/tests/integration/media/test_discovery_search.py`: `SearchProvider(kind="media")` conformance (008 kit) with type/genre/year/availability filters; shelves `new|recent|continue|trending|recommended` permission/privacy-bounded; no dead-end empty states (next action)
- [ ] T028 [US7] Implement `MD/providers/search.py` (+ `ObjectResolver`), `MD/discovery/{shelves,baseline_recommender}.py` (deterministic genre/people affinity + 017 popularity), `GET /media/discovery/{shelf}`, and `FM/home/Shelves.tsx`

## Phase 10: US8 + US9 — AI and Community integration (P2/P3)
- [ ] T029 [P] [US8] Write `backend/tests/security/media/test_ai_tools.py`: AI read tools (catalog search, my history, recommendations) run as the acting principal; never return another user's private history; no secrets/source URLs in outputs
- [ ] T030 [P] [US9] Write `backend/tests/integration/media/test_community_context.py`: Media object references usable by Community with public summary; concerned-users/ratings only within owners' visibility; erased users disappear without breaking references
- [ ] T031 [US8] Implement `MD/providers/ai_tools.py` (tool definitions for 018) and `MD/providers/community.py` (`MediaCatalog.resolve_ref` + public summary)

## Phase 11: US11 — Extensibility (P2)
- [ ] T032 [P] [US11] Write `backend/tests/contract/media/test_extensibility.py`: new media type registered without touching core; plugin detail block and palette action appear permission-gated; statistics pack and widgets register; plugin disable removes contributions gracefully
- [ ] T033 [US11] Ship statistics packs `backend/definitions/packs/{media,playback,reading,gaming}.json` (017), widgets `media.continue|recent|now_playing|requests` (009), notification categories (010), palette actions (008), and `docs/media-extensibility.md`

## Phase 12: Polish & cross-cutting
- [ ] T034 [P] Register `media` with Observability (catalog freshness per service, poll health, candidate queue size, unlinked activity, section latency) in `MD/observability.py`
- [ ] T035 [P] Write `backend/tests/security/media/test_privacy_secrets.py`: no secrets/credential URLs in payloads, responses, events or logs; history/links/requests not visible to others; admin views metadata only
- [ ] T036 [P] Add `/media*`, `/me/media*`, `/admin/media/*` to the permission-matrix test, regenerate OpenAPI client, write `docs/media.md` (identity/matching, field priority, history semantics, building a connector with the kits)

## Cross-spec obligations (audit 2026-10-01 — see `decisions/PLAN_FOLLOWUPS.md`)
- [ ] T037 Register Media's `ActivityAttributeProvider` (media kind, canonical genre tags, original/effective title) for media events, used by 014 campaign and 019 automation conditions; test `backend/tests/contract/media/test_activity_attributes.py` (F6)
- [ ] T038 [P] Expose owner-tagged registration on the media type and detail-block registries: `register(..., owner="module:<id>|plugin:<key>")` and `unregister(owner)`, with a test in `backend/tests/unit/media/test_registry_owner.py` proving all contributions of an owner disappear (required by 023's conformance sweep, F20)

- [ ] T039 Run `specs/024-media/quickstart.md` end-to-end; record deviations and open product confirmations (OQ-115..119 defaults)

## Dependencies & Order
Setup → Foundational → US1/US2 (MVP) → US10 → US3 → US4 → US5 → US6 → US7 → US8/US9 → US11 → Polish. US10 feeds US3's sources section; US5 needs US4 events; US7 needs history + 008/017; US11 extension points can be wired once US3/US7 exist.
**Parallel examples**: T004/T005 · T009/T010/T011 · T018/T019 · T029/T030 · T034/T035/T036.
**MVP**: Phases 1–3 (capabilities, library sink, identity + field resolution, catalog API/UI, admin matching).

## Format validation
39 tasks, all checkbox + ID + path; story labels only on story phases.
