---
description: "Task list — Portal Observability (spec 025)"
---

# Tasks: Portal Observability

**Input**: `specs/025-observability/` · **Branch**: `025-observability` · **Roadmap**: Phase 2 step 7 · **Tests**: included.
Abbrev: **`OB/`** = `backend/src/portalab/modules/observability`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` kernel · `D-003` authz · `D-007` events · `D-020` config · `D-021` retention/partitions · `D-005/006` inputs · ports `support.incidents` (016) and `notifications.send_alert` (010) are stubs until those specs land.

## Phase 1: Setup
- [ ] T001 Create `OB/{collector,errors,components,detectors,escalation,overview,alerts,api,models}/__init__.py`, `backend/migrations/observability/versions/`, `backend/tests/{unit,integration,security}/observability/`, `frontend/src/features/admin/observability/`
- [ ] T002 [P] Declare settings (`observability.sampleRetentionDays`, `.rollupRetentionMonths`, `.errorRetentionDays`, `.detectors.<name>.*`, `.escalation.autoSeverity`, `.escalation.requireValidation`, `.thresholds.<component>.*`, `.metricsEndpointEnabled`) in `OB/settings.py`
- [ ] T003 [P] Declare permissions `observability.read`, `observability.manage` (audited) in `OB/permissions.py`; register retention targets for samples/rollups/errors

## Phase 2: Foundational — kernel hooks & data
### Tests first
- [ ] T004 [P] Write `backend/tests/unit/test_metrics_hooks.py`: counters/histograms/`Timer(phase)` are non-blocking; full queue drops oldest and counts drops; hooks never raise into callers
- [ ] T005 [P] Write `backend/tests/integration/observability/test_schema.py`: tables, partitioned `metric_samples`, `health_history` append-only, unique error fingerprint
### Implementation
- [ ] T006 Implement `backend/src/portalab/core/metrics.py` (registry, bounded queue, `Timer`, `errors.record` hook, redaction) and retrofit it into `core.jobs`, `ConnectorHttpClient`, the app middleware (phases `portal_wait|external_wait|internal|timeout`)
- [ ] T007 Implement models + Alembic revision for all `obs.*` tables (partitions via 021 helper)
- [ ] T008 Implement `OB/collector/job.py` (drain queue, minute aggregation, `metric_samples`, hourly/daily rollups, pruning) and its fail-open test `backend/tests/integration/observability/test_failopen.py` (store down ⇒ requests unaffected, drops counted)

## Phase 3: US7 — Structured errors (P1)
- [ ] T009 [P] [US7] Write `backend/tests/unit/observability/test_error_recorder.py`: fingerprint stable across volatile parts; 50 occurrences ⇒ one row count 50; first/last seen; secrets/tokens/PII redacted from message and context; no generic un-diagnosable record (component/category required)
- [ ] T010 [US7] Implement `OB/errors/recorder.py` and error lifecycle (ack/resolve with resolution text) + routers `GET /admin/observability/errors`, `POST …/ack|resolve`

## Phase 4: US2 — Technical vs functional health (P1) 🎯 MVP
- [ ] T011 [P] [US2] Write `backend/tests/unit/observability/test_health_evaluator.py`: table-driven — technical ok + functional failing ⇒ reported degraded (never "healthy"); both axes independent; evaluator failure ⇒ `unknown` not green; thresholds from config
- [ ] T012 [US2] Implement `OB/components/registry.py` (`declare_observable`, `FunctionalCheck`, `TechnicalCheck`) and `OB/components/evaluator.py` writing `component_health`/`health_history` and emitting `observability.health_changed`
- [ ] T013 [US2] Add the `observability.health` capability and `GET /admin/observability/components/{id}`

## Phase 5: US3/US4/US5 — Adapters for events, sync, automations, plugins, connectors, AI (P1)
### Tests first
- [ ] T014 [P] [US3] Write `backend/tests/integration/observability/test_adapters_core.py`: consumer lag/dead letters ⇒ events component; service reachable but sync failing ⇒ functional failing while 006 state stays Operational; automation suspended/loop reason visible; job queue and DB components
- [ ] T015 [P] [US4] Write `backend/tests/integration/observability/test_adapters_extensions.py`: plugin states (active/disabled/error/incompatible/invalid-config/missing-dependency, version, last activity, recent errors); a failing plugin leaves the portal available; connector complement distinguishes functional vs external-unavailable vs invalid-auth vs sync-error vs stale
- [ ] T016 [P] [US5] Write `backend/tests/security/observability/test_ai_metadata_only.py`: AI metrics carry counts/latency/errors/timeouts/provider/model/tools/actions/failure-rate and **no prompt/response content** anywhere in `obs.*`
### Implementation
- [ ] T017 [US3] Implement adapters in `OB/components/adapters/` for events (007), sync (005), automations (019 stub until it lands), jobs, database, portal-global; register via `declare_observable`
- [ ] T018 [US4] Implement `declare_observable` consumption for plugins/connectors (common model) and the plugin/connector adapters
- [ ] T019 [US5] Implement the AI adapter contract (metrics-only reporting API for spec 018) in `OB/components/adapters/ai.py`

## Phase 6: US6 — Performance attribution (P2)
- [ ] T020 [P] [US6] Write `backend/tests/integration/observability/test_performance_phases.py`: slow external call ⇒ `external_wait`; slow handler ⇒ `internal`; timeouts counted; slow page/widget/search/sync/automation views list the dominant phase; no fixed threshold in code
- [ ] T021 [US6] Implement `OB/components/performance.py` (per-route/per-component phase aggregation, config thresholds) and the performance view endpoint `GET /admin/observability/performance`

## Phase 7: US7 — Anomalies and escalation (P1)
- [ ] T022 [P] [US7] Write `backend/tests/unit/observability/test_detectors.py`: error-rate spike vs baseline, abnormally long sync, repeated automation, stuck consumer, latency spike, repeated failure — each on synthetic series with parameters from config; an anomaly is **not** an incident by itself
- [ ] T023 [P] [US7] Write `backend/tests/integration/observability/test_escalation.py`: policy auto/human validation; repeated anomalies with one fingerprint attach to a single open incident via the `support.incidents` port; port down ⇒ stays `pending_validation` and retries; no local incident table exists
- [ ] T024 [US7] Implement `OB/detectors/` (registry + the six rule-based detectors) and `OB/escalation/service.py`; routers `GET /admin/observability/anomalies`, `POST …/validate|dismiss`

## Phase 8: US8/US1 — Alerts, diagnostics, overview (P1)
- [ ] T025 [P] [US8] Write `backend/tests/integration/observability/test_alerts_diagnostics.py`: alert conditions go through `notifications.send_alert` (stub) and publish events usable by Automations; diagnostic descriptors point to owners' APIs with their permissions; executing a sensitive action is audited by the owner
- [ ] T026 [P] [US1] Write `backend/tests/integration/observability/test_overview_ranking.py`: problems ranked action-needed → impact → criticality → age → details; not a flat metric list; panel degrades alone
- [ ] T027 [US8] Implement `OB/alerts/service.py` and `DiagnosticAction` descriptors (rerun sync/job, test connector, disable automation, open/create incident, view history, ask-AI placeholder)
- [ ] T028 [US1] Implement `OB/overview/service.py`, `GET /admin/observability/overview`, and register the Control Center panel + required-actions provider with 020

## Phase 9: US9/US10/US11 — Permissions, trends, extensibility, polish
- [ ] T029 [P] [US9] Write `backend/tests/security/observability/test_permissions_privacy.py`: standard users denied by default; Support gets redacted context, Admin full; no secrets/tokens in samples/errors/logs; user references only ids and only when permitted
- [ ] T030 [P] [US10] Write `backend/tests/integration/observability/test_trends_retention.py`: trends over periods; detailed samples expire before rollups; observability data separable from user functional data
- [ ] T031 [US10] Implement `GET /admin/observability/trends` and the retention targets (T003)
- [ ] T032 [US11] Implement the optional `/metrics` endpoint (disabled by default, token/permission protected) and the observability self-component (queue depth, drops, collector lag)
- [ ] T033 [P] Admin UI in `frontend/src/features/admin/observability/` (overview, components, errors, anomalies, trends) with loading/error/unauthorized states, non-color-only status, keyboard, axe, externalized strings
- [ ] T034 Permission-matrix test for all observability routes (`backend/tests/security/test_permission_matrix.py`), migration-upgrade test `backend/tests/migrations/test_upgrade_observability.py` (006 → obs) and full validation; record results

## Dependencies & Execution Order
Setup → Foundational (T006 retrofit first) → errors → **health evaluator (MVP)** → adapters → performance → detectors/escalation → alerts/overview → trends/UI. Ports to 016/010 are stubs until those specs.

## Traceability (FR → tasks)
FR-001/002 T012, T017 · FR-003..005 T011–T013 · FR-006..008 T014, T017 · FR-009/010 T015, T018 · FR-011/012 T016, T019 · FR-013/014 T020, T021 · FR-015/016 T009, T010 · FR-017..019 T022–T024 · FR-020..022 T025, T027 · FR-023..025 T026, T028 · FR-026..028 T030, T031 · FR-029..031 T029 · FR-032/033 T008 · FR-034 T018 · FR-035 (indexing) via provider in 008 plan · FR-036 events T012, T024 · FR-037 AI use via 018 plan.
Total: **34 tasks**. MVP = Setup + Foundational + errors + health evaluator.
