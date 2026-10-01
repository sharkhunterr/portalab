---
description: "Task list — Statistics (spec 017)"
---

# Tasks: Statistics

**Input**: `specs/017-statistics/` · **Branch**: `017-statistics` · **Roadmap**: Phase 4 step 14 · **Tests**: included.
Abbrev: **`ST/`** = `backend/src/portalab/modules/statistics`, **`CAP/`** = `backend/src/portalab/capabilities/statistics`, **`FS/`** = `frontend/src/features/statistics`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` kernel/jobs · `D-003` authz + `ConfirmationService` · `D-007` events (consumer API, `idempotent_effect`, replay, aggregatable-field registry) · `D-020` settings · `D-021` visibility/retention · `D-009` widget registry · `D-022` `Chart` wrapper/states · `D-026` formatting · `D-006` service health · `D-025` health. Ports `ProgressionReader` (013), `EntitlementReader` (015), `CampaignReader` (014), `notifications.send` (010) are stubs until those specs land.

## Phase 1: Setup
- [ ] T001 Create `CAP/__init__.py`, `ST/{definitions,packs,projection,period,unlock,privacy,provider,trend,wrapped,api,models}/__init__.py`, `backend/migrations/stats/versions/`, `backend/definitions/packs/`, `FS/{charts,cards,wrapped,preferences}/`, `backend/tests/{unit,integration,contract,security}/statistics/`, `frontend/tests/{unit,e2e}/statistics/`
- [ ] T002 [P] Add `recharts` dependency; declare settings (`statistics.timezone`, `.firstDayOfWeek`, `.defaultMinCohortSize`, `.staleAfterSeconds`, `.maxBucketsPerRequest`, `.bucketRetentionMonths`, `.wrapped.enabled`, user `statistics.hiddenSections`) in `ST/settings.py`; permissions `statistics.read` (default grant), `statistics.manage` (audited) in `ST/permissions.py`
- [ ] T003 [P] Register retention targets (buckets/members/snapshots) with 021, classify personal buckets/snapshots (`activity`) in the PII registry, and register the 020/021 export+erasure participant `ST/privacy.py` (personal buckets deleted, community aggregates retained)

## Phase 2: Foundational — definition model, schema, field registry
### Tests first
- [ ] T004 [P] Write `backend/tests/unit/statistics/test_definition_schema.py`: closed measure/dimension set; unknown or non-aggregatable field rejected; unlock tree validation; min cohort ≥ configured floor; no free expressions
- [ ] T005 [P] Write `backend/tests/integration/statistics/test_schema.py`: tables, append-only `definitions`, composite PKs, FK only to `identity.users(id)`
### Implementation
- [ ] T006 Implement `CAP/` contracts (`StatisticDefinition`, `StatResult`, `Period`, `StatisticsProvider`, ports) and `ST/models` + Alembic revision for schema `stats`
- [ ] T007 Implement `ST/definitions/service.py` (validate against 007 aggregatable-field registry, version, activate/retire, audit via `AuditSink`, emit `statistics.definition_changed`) and `ST/packs/registry.py` (`register_definition_pack`; plugin packs inactive)

## Phase 3: US2 — Computed from history/events, permission/privacy-bounded (P1) 🎯 MVP
**Independent test**: seed events, compare buckets to an oracle query; viewers only receive what they are permitted to see.
- [ ] T008 [P] [US2] Write `backend/tests/integration/statistics/test_projection.py`: bucket totals equal oracle SQL over seeded events; duplicate event ⇒ no double count; out-of-order event lands in its `occurred_at` day; replay (`ReplayService`) reproduces identical buckets; consumer crash resumes without loss
- [ ] T009 [P] [US2] Write `backend/tests/unit/statistics/test_period.py`: day/week/month/quarter/year/last_n_days boundaries in statistics tz incl. DST days and configurable first day of week; deterministic across calls
- [ ] T010 [P] [US2] Write `backend/tests/security/statistics/test_privacy.py`: personal statistic owner-only; other-subject access follows 021 visibility; community stat below cohort ⇒ `insufficient_data`; small dimension cells suppressed/merged; no leakage through totals vs breakdown difference
- [ ] T011 [US2] Implement `ST/projection/consumers.py` (dynamic consumer set per active definition event types, `ctx.idempotent_effect`, bucket/members upserts) and rebuild path via `ReplayService`
- [ ] T012 [US2] Implement `ST/period/resolver.py` and `ST/privacy/guard.py` (cohort suppression, subject visibility)
- [ ] T013 [US2] Implement `ST/provider/provider.py` (`StatisticsProvider.get/catalog`: permission, privacy, bucket cap, roll-up, `as_of` from consumer watermark) and routers `GET /statistics/catalog`, `GET /statistics/{key}`

## Phase 4: US1 — Consume admin-defined statistics: choose, filter, period, hide (P1)
- [ ] T014 [P] [US1] Write `frontend/tests/unit/statistics/consumption.test.tsx`: catalog selection, period picker, filters update without page reset; hide only where `hideable`; non-hideable sections cannot be hidden; no UI exists to create charts/queries
- [ ] T015 [P] [US1] Write `backend/tests/integration/statistics/test_authorship.py`: only `statistics.manage` can create/edit definitions; users get 403 on admin routes; hidden-section preference rejected for non-hideable definitions
- [ ] T016 [US1] Implement `FS/StatisticsPage.tsx`, `charts/StatChart.tsx` (Recharts + accessible data table/summary, pattern+label not color-only), `cards/StatCard.tsx`, `preferences/HiddenSections.tsx` and `GET/PUT /me/statistics/preferences`
- [ ] T017 [US1] Implement admin routers `GET/POST/PUT /admin/statistics/definitions[/{key}]`, `POST …/activate|retire|rebuild` (rebuild with `ConfirmationService`, `stats.rebuild_runs`) and admin definition editor screen `FS/admin/DefinitionEditor.tsx` (form from schema, preview)

## Phase 5: US5 — Unlockable statistics (P1)
- [ ] T018 [P] [US5] Write `backend/tests/integration/statistics/test_unlock.py`: level/achievement/product/campaign/combination conditions via stub ports; locked ⇒ no bucket query executed and only hint returned; meeting condition makes it viewable; relock semantics (campaign/product relock, level/achievement persisted in `stats.unlocks`); port failure fails closed; `statistics.unlocked` emitted once
- [ ] T019 [US5] Implement `ST/unlock/evaluator.py`, `stats.unlocks` persistence, port stubs under `CAP/ports.py`, and provider integration (short-circuit before computation)

## Phase 6: US6 — Engine feeds other systems (P1)
- [ ] T020 [P] [US6] Write `backend/tests/contract/statistics/test_consumer_consistency.py`: same stat/subject/period/filters yield identical values through API, dashboard bridge, a gamification-style internal call and an AI-tool call (principal-bounded); a consumer without permission gets nothing; results never include secrets
- [ ] T021 [US6] Implement dashboard widget bridge `ST/widgets.py` (`register_widget` for `statistics.card`, provider via `StatisticsProvider`) and documented client for other consumers (`docs/statistics-provider.md`); add `search`/palette entry only through existing registries

## Phase 7: US4 + US3 — Cross-service and domain coverage (P2)
- [ ] T022 [P] [US4] Write `backend/tests/integration/statistics/test_cross_service.py`: aggregation over events from multiple services with canonical-reference dedup; one source down ⇒ `partial` with `source_states`; stale watermark ⇒ `stale` with `as_of`; unrelated statistics unaffected
- [ ] T023 [P] [US3] Write `backend/tests/contract/statistics/test_domain_coverage.py`: checklist of domain packs (media, playback, reading, gaming, community, gamification, services, requests, users, activity, trends) — passes for registered packs, reports pending ones with owner spec
- [ ] T024 [US4] Implement source-state resolution in provider (`health.service_state` + projection watermark → `partial|stale|unavailable`)
- [ ] T025 [US3] Ship starter packs `backend/definitions/packs/users.json` (active users by day, sign-ins) and `services.json` (service availability over time) plus pack template/docs for domain specs

## Phase 8: US8 — Visualization, trends, degraded states (P2)
- [ ] T026 [P] [US8] Write `backend/tests/unit/statistics/test_trend.py`: delta/direction versus previous period of equal length; empty previous period ⇒ no misleading percentage; deterministic
- [ ] T027 [P] [US8] Write `frontend/tests/a11y/stat-states.spec.tsx`: loading/available/partial/stale/error/unavailable/locked/insufficient_data/no_data via `FunctionalState` across themes; table alternative present; keyboard navigation of chart legend/table
- [ ] T028 [US8] Implement `ST/trend/calculator.py`, trend rendering in `StatChart`, ETag/short-TTL caching and `statistics.too_many_buckets` guidance in provider/UI

## Phase 9: US7 — Wrapped (P2)
- [ ] T029 [P] [US7] Write `backend/tests/integration/statistics/test_wrapped.py`: generation per user from admin-defined stats respecting permissions/unlocks; snapshot immutable and owner-only; community Wrapped applies cohort thresholds; delivery via `notifications.send` stub honors preferences, in-app works without it; failure for one user does not block others; erased with account
- [ ] T030 [US7] Implement `ST/wrapped/service.py` (definitions, generation job, snapshots, delivery), routers `/me/wrapped*`, `/wrapped/community/{period}`, `/admin/statistics/wrapped*`, and `FS/wrapped/WrappedStory.tsx` (accessible, reduced-motion aware)

## Phase 10: Polish & cross-cutting
- [ ] T031 [P] Implement admin `GET /admin/statistics/status` (lag, rebuild runs) and Observability registration (functional freshness check, metrics) in `ST/observability.py`; handle `admin.config_changed` for tz/first-day (flag rebuild required)
- [ ] T032 [P] Add `/statistics*`, `/me/statistics*`, `/me/wrapped*`, `/admin/statistics/*` to the permission-matrix test, regenerate OpenAPI client, write `docs/statistics.md` (definition authoring, pack format, time semantics, privacy thresholds)
- [ ] T033 Run `specs/017-statistics/quickstart.md` end-to-end; record deviations and open product confirmations (OQ-80..84 defaults)

## Dependencies & Order
Setup → Foundational → US2 (MVP) → US1 → US5 → US6 → US4/US3 → US8 → US7 → Polish. US5 needs the provider from US2; US6 needs provider + 009 registry; US7 needs unlock + privacy + provider; domain packs from other specs plug in after US3.
**Parallel examples**: T004/T005 · T008/T009/T010 · T014/T015 · T022/T023 · T031/T032.
**MVP**: Phases 1–3 (definitions, deterministic projection, permission/privacy-bounded provider and API).

## Format validation
33 tasks, all checkbox + ID + path; story labels only on story phases.
