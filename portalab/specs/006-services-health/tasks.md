---
description: "Task list — Services & Health (spec 006)"
---

# Tasks: Services & Health

**Input**: `specs/006-services-health/` · **Branch**: `006-services-health` · **Roadmap**: step 6 (backend) and step 13 (detail UI, incident links) · **Tests**: included.
Abbrev: **`HL/`** = `backend/src/portalab/modules/health`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-005` services/breaker/sync state · `D-003` authz · `D-007` publisher · `D-020` config · `D-021` retention/partitions · `D-016` `support.incidents` provider (port only until Support lands).

## Phase 1: Setup
- [ ] T001 Create `HL/{probes,state,rollups,maintenance,infra,operations,detail,api,models}/__init__.py`, `backend/migrations/health/versions/`, `backend/tests/{unit,integration,security}/health/`, `frontend/src/features/services/`
- [ ] T002 [P] Declare settings `health.probeIntervalSeconds`, `health.degradedLatencyMs`, `health.unavailableAfterFailures`, `health.staleAfterSeconds`, `health.sampleRetentionDays`, `health.infraRetentionDays`, `health.rollupRetentionMonths` in `HL/settings.py`
- [ ] T003 [P] Declare permission `infrastructure.read` and register retention targets (samples, infra samples) in `HL/permissions.py`, `HL/retention.py`

## Phase 2: Foundational
### Tests first
- [ ] T004 [P] Write `backend/tests/integration/health/test_schema.py`: tables, partitioned samples, `state_history` append-only, unique rollup bucket
- [ ] T005 [P] Write `backend/tests/unit/health/test_state_deriver.py`: table-driven — probes ok ⇒ Operational; latency over threshold ⇒ Degraded; N failures ⇒ Unavailable; no signal/stale ⇒ Unknown (never Operational); active maintenance ⇒ Maintenance (not Unavailable) and reverts after; breaker open ⇒ Unavailable
### Implementation
- [ ] T006 Implement models + Alembic revision for all `health.*` tables
- [ ] T007 Implement `HL/state/deriver.py` (pure function, versioned rules) and `HL/state/service.py` (write `service_state`/`state_history`, emit `service.status_changed` with dedup `(service, to_state, state_seq)`)

## Phase 3: US1/US5 — Service state at a glance, monitoring (P1) 🎯 MVP
- [ ] T008 [P] [US1] Write `backend/tests/integration/health/test_probes.py`: probe jobs write samples; outage ⇒ Unavailable once (single event); recovery ⇒ Operational; per-service isolation; monitor failure ⇒ Unknown
- [ ] T009 [US5] Implement `HL/probes/scheduler.py` and `HL/probes/runner.py` (job `probe_service`, capability `service.health_probe`, timeout, sample + recent-error recording)
- [ ] T010 [US1] Implement the `health.service_state` capability in `HL/state/capability.py` (value with `as_of`) and register it
- [ ] T011 [US1] Add routers `GET /services/health` and the state part of `GET /services/{id}/health` in `HL/api/health.py` (`services.read`)

## Phase 4: US5/US4 — Availability, uptime, errors, history (P2)
- [ ] T012 [P] [US4] Write `backend/tests/integration/health/test_rollups_history.py`: hourly rollups compute availability/downtime with gaps marked; history uses `occurred_at`; history distinct from incidents and sync history
- [ ] T013 [US4] Implement `HL/rollups/job.py` (hourly rollups, pruning by retention) and `HL/rollups/availability.py`
- [ ] T014 [US4] Add `GET /services/{id}/health/history` and the recent-errors section in `HL/api/history.py`

## Phase 5: US1 — Maintenance windows (P1)
- [ ] T015 [P] [US1] Write `backend/tests/integration/health/test_maintenance.py`: schedule/cancel; jobs flip to Maintenance/back at absolute instants; missed job reconciled at startup; events `maintenance.scheduled|started|ended|cancelled`; reference time zone stored for wall-clock intents
- [ ] T016 [US1] Implement `HL/maintenance/service.py` + jobs `maintenance_start`/`maintenance_end` and routers `GET|POST|PATCH|DELETE /maintenance`, `GET /services/{id}/maintenance` (`services.manage`, cancel sensitive)

## Phase 6: US2/US6 — Permission-tiered infrastructure and operations (P1/P2)
### Tests first
- [ ] T017 [P] [US2] Write `backend/tests/security/health/test_visibility_tiers.py`: standard user gets state/availability only; `infrastructure.read` adds metrics; `services.manage` adds operations; enforced server-side, not by UI
- [ ] T018 [P] [US6] Write `backend/tests/integration/health/test_infra_operations.py`: metrics with per-metric `NotAvailable` (never zero); partial provider ⇒ other metrics shown; operation requires confirmation + audit; unreachable host ⇒ actionable error
### Implementation
- [ ] T019 [US6] Implement `HL/infra/service.py` (capability `infrastructure.metrics`, storage in `infra_samples`, retention) and `GET /services/{id}/health/infrastructure`
- [ ] T020 [US6] Implement `HL/operations/service.py` (capability `server.operations`, sensitive, confirmation, `service.operation_performed`) and routers `GET|POST /services/{id}/operations`

## Phase 7: US3/US7 — Detail page and degraded mode (P1)
- [ ] T021 [P] [US3] Write `backend/tests/integration/health/test_detail_sections.py`: sections independent (state, availability, errors, maintenance, incidents, tickets, sync, infra, history); a failing/slow section reports its own state while others render; Service State, Incident, Maintenance, Ticket and Sync State remain distinct elements
- [ ] T022 [US3] Implement `HL/detail/assembler.py` (per-section timeout/state, permission tiers) and `GET /services/{id}/health` full response
- [ ] T023 [US3] Implement `HL/detail/incidents.py` using the `support.incidents` port (`open_for_service`, `link`) with an empty-provider default and `health.service_incident_links`

## Phase 8: Polish & validation (UI at roadmap step 13)
- [ ] T024 [P] Build `frontend/src/features/services/` overview and detail page (state badges non-color-only, sections with loading/error/unavailable/stale states, tier-aware rendering, keyboard, axe, externalized strings)
- [ ] T025 [P] Add observability in `HL/observability.py` (probe latency/failures, state changes, section failures, rollup lag) with redaction test
- [ ] T026 Permission-matrix test for all health routes, migration-upgrade test (005 → health) and full validation; record results

## Dependencies & Execution Order
Setup → Foundational → **US1/US5 (MVP)** → availability/history → maintenance → tiers/infra/operations → detail assembler → Polish. UI work (T024) is scheduled with roadmap step 13; backend tasks T001–T023 belong to step 6.

## Traceability (FR → tasks)
FR-001..004 T005, T007, T021 · FR-005..009 T008, T009, T012–T014 · FR-010..012 T017 · FR-013..015 T018, T019 · FR-016..018 T018, T020 · FR-019..022 T021, T023 · FR-023..025 T012–T014 · FR-026..029 T021, T022, T024 · FR-030/031 T021 · FR-032/033 T007, T016, T020.
Total: **26 tasks**. MVP = Setup + Foundational + US1/US5.
