---
description: "Task list — Connectors (spec 005)"
---

# Tasks: Connectors

**Input**: `specs/005-connectors/` · **Branch**: `005-connectors` · **Roadmap**: Phase 2 step 6 · **Tests**: included.
Abbrev: **`CN/`** = `backend/src/portalab/modules/connectors`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` registry/jobs/secrets · `D-003` authz/audit · `D-007` publisher · `D-020` toggles/config · `D-021` purge/retention. Real connectors (Plex, Radarr, …) are **not** part of this list.

## Phase 1: Setup
- [ ] T001 Create `CN/{sdk,registry,services,discovery,sync,breaker,http,api,models}/__init__.py`, `backend/src/portalab/connectors/fake/`, `backend/migrations/connectors/versions/`, `backend/tests/{unit,integration,contract,security}/connectors/`
- [ ] T002 [P] Declare settings (`connectors.defaultSyncIntervalSeconds`, `connectors.circuit.*`, `connectors.http.*`, `connectors.fieldPriority.<domain>`, `connectors.resync.confirmDeleteRatio`) in `CN/settings.py`
- [ ] T003 [P] Declare permissions `services.read`, `services.manage`, `connectors.manage` (sensitive) in `CN/permissions.py` (`services.purge` comes from 021)

## Phase 2: Foundational
### Tests first
- [ ] T004 [P] Write `backend/tests/integration/connectors/test_schema.py`: tables/constraints, `sync_runs` append-only, unique service+capability
- [ ] T005 [P] Write `backend/tests/unit/connectors/test_registry.py`: duplicate connector keys rejected; manifest validated; config schema/secret fields declared
### Implementation
- [ ] T006 Implement models + Alembic revision for all `connectors.*` tables
- [ ] T007 Implement the SDK in `CN/sdk/` (`Connector`, `Manifest`, `SourceRecord`, `SyncProgress`, `TestResult`, `Candidate`) and `CN/registry/connectors.py`
- [ ] T008 Implement `CN/http/client.py` `ConnectorHttpClient` (timeouts, max response size, same-host redirects, retry/backoff, TLS option, correlation id, secret redaction) with `backend/tests/unit/connectors/test_http_client.py`

## Phase 3: US1 — Add a service without changing modules (P1) 🎯 MVP
### Tests first
- [ ] T009 [P] [US1] Write `backend/tests/integration/connectors/test_capability_provision.py`: enabling a service provides its capabilities; consumer resolves without naming the service; two services for one capability ordered by priority; disabling withdraws and keeps data
- [ ] T010 [P] [US1] Write `backend/tests/integration/connectors/test_service_lifecycle.py`: configured → enabled → disabled → disconnected transitions, `service.connected|status_changed|disconnected` events, credentials never returned
### Implementation
- [ ] T011 [US1] Implement `CN/services/manager.py` (state machine, enable/disable/disconnect, capability provide/withdraw via the 001 registry, event emission, audit)
- [ ] T012 [US1] Implement the `fake` connector in `backend/src/portalab/connectors/fake/` (configurable latency/failure/garbage, one capability, deterministic records)
- [ ] T013 [US1] Add routers `GET /connectors`, `GET|POST|PATCH /services`, `POST /services/{id}/enable|disable|disconnect` in `CN/api/services.py` (write-only secrets)

## Phase 4: US3/US9 — Connection test and compatibility (P1/P2)
- [ ] T014 [P] [US3] Write `backend/tests/integration/connectors/test_connection_test.py`: pass/fail with actionable diagnostics; never changes enable/disable state; secrets redacted
- [ ] T015 [P] [US9] Write `backend/tests/unit/connectors/test_compatibility.py`: incompatible portal version/capability/permission ⇒ refuse or warn with reason; prior working state preserved
- [ ] T016 [US3] Implement `CN/services/tester.py` and router `POST /services/{id}/test`
- [ ] T017 [US9] Implement `CN/services/compatibility.py` and register the compatibility hook with the 020 toggle service

## Phase 5: US2 — Discovery and manual configuration (P2)
- [ ] T018 [P] [US2] Write `backend/tests/integration/connectors/test_discovery.py`: probes only operator-supplied targets; candidates need explicit confirm; decline keeps them re-offerable; never auto-enabled
- [ ] T019 [US2] Implement `CN/discovery/service.py` and routers `POST /connectors/{key}/discover`, `POST /discovery/{id}/confirm|decline`

## Phase 6: US5/US6 — Synchronization, errors, history, source of truth (P1)
### Tests first
- [ ] T020 [P] [US5] Write `backend/tests/integration/connectors/test_sync_runner.py`: run recorded with counts; duplicate/late records idempotent; sink failure marks batch failed without rolling back earlier batches; overlapping trigger skipped; `occurred_at` not replaced by sync time
- [ ] T021 [P] [US6] Write `backend/tests/integration/connectors/test_source_of_truth.py`: removed-at-source ⇒ deactivated not deleted; failed/partial sync deletes nothing; conflicts resolved by configured field priority with provenance kept
- [ ] T022 [P] [US5] Write `backend/tests/contract/test_record_sink_kit.py`: reusable sink contract (idempotent upsert, deactivate, provenance, no deletes)
### Implementation
- [ ] T023 [US5] Implement `CN/sync/runner.py` (advisory lock per service, cursor checkpointing, counts, history, events `sync.started|completed|failed`) and `CN/sync/scheduler.py` (job `sync_service`, dedup `(service, window)`)
- [ ] T024 [US6] Implement the `RecordSink` registry/contract in `backend/src/portalab/capabilities/record_sink.py` and the field-priority reconciler in `CN/sync/reconcile.py`
- [ ] T025 [US5] Add routers `POST /services/{id}/sync`, `GET /services/{id}/sync-runs` in `CN/api/sync.py`

## Phase 7: US4 — State, resilience, circuit breaker (P1)
- [ ] T026 [P] [US4] Write `backend/tests/unit/connectors/test_breaker.py` and `backend/tests/integration/connectors/test_outage.py`: repeated failures open the breaker ⇒ state `unavailable`; half-open probe recovers; last-known data served as stale; unrelated services unaffected; sync state and health reported separately
- [ ] T027 [US4] Implement `CN/breaker/breaker.py` and integrate it with the 001 provider isolation wrapper and `ServiceManager.state`

## Phase 8: US7/US8 — Resync and disconnection (P2/P1)
- [ ] T028 [P] [US7] Write `backend/tests/integration/connectors/test_resync.py`: full resync reconciles only that service's provenance, never native portal data; large deletion ratio requires confirmation; audited
- [ ] T029 [P] [US8] Write `backend/tests/integration/connectors/test_disconnect.py`: disconnect withdraws capabilities, stops sync, keeps history marked historical/stale; purge only via `services.purge`
- [ ] T030 [US7] Implement resync (partial/full, delete-ratio guard) in `CN/sync/resync.py` and router `POST /services/{id}/resync` with confirmation
- [ ] T031 [US8] Implement disconnect semantics and the `historical/stale` marker exposure in `CN/services/manager.py`; wire the 021 purge hook to enumerate this service's data

## Phase 9: Polish & validation
- [ ] T032 [P] Implement the `ConformanceKit` in `backend/src/portalab/connectors/conformance.py` (health, timeouts, garbage payloads, auth errors, idempotent sync) and run it against the `fake` connector
- [ ] T033 [P] Add observability in `CN/observability.py` (state, last success, run duration/counts, breaker, latency) with redaction test
- [ ] T034 [P] Admin UI in `frontend/src/features/admin/services/` (list, configure + test, enable/disable, sync history) with states, keyboard, axe, externalized strings

## Cross-spec obligations (audit 2026-10-01 — see `decisions/PLAN_FOLLOWUPS.md`)
- [ ] T035 Read per-field source-priority tables from the shape defined by 024 (`media.fieldPriority.<kind>.<field>`, CD-026) instead of a separate connectors key; document it in `docs/connectors.md` (F7)
- [ ] T036 Register automation action types `connector.sync` and `connector.action` (019) through the owners' action contract in `CN/automation.py`, with permission and idempotency; test `backend/tests/contract/connectors/test_automation_actions.py` (F14)
- [ ] T037 Register the optional, skippable `services` step of the Admin first-run wizard (020 `FirstRunStep`) in `CN/firstrun.py`: list available connectors and configure first services (decided 2026-10-01: Admin wizard only, not user onboarding)
- [ ] T038 [P] Expose owner-tagged registration on the connector/capability registries: `register(..., owner="module:<id>|plugin:<key>")` and `unregister(owner)`, with a test in `backend/tests/unit/connectors/test_registry_owner.py` proving all contributions of an owner disappear (required by 023's conformance sweep, F20)

- [ ] T039 Permission-matrix test (`backend/tests/security/test_permission_matrix.py`), migration-upgrade test `backend/tests/migrations/test_upgrade_connectors.py` (007 → connectors) and full validation; record results

## Dependencies & Execution Order
Setup → Foundational → **US1 (MVP)** → US3/US9 → US2 → US5/US6 → US4 → US7/US8 → Polish. T024 sink contract precedes T023 use in domain plans. Real connectors come with Media (024) and later domains.

## Traceability (FR → tasks)
FR-001..004 T009–T012, T024 · FR-005/006 T018, T019, T013 · FR-007 T013, T016 · FR-008/009 T014, T016 · FR-010..013 T010, T011, T026, T027 · FR-014..018 T020, T023, T025 · FR-019..021 T021, T024 · FR-022..024 T028, T030 · FR-025..028 T029, T031 · FR-029 T015, T017 · FR-030..032 T003, T013, T039 · FR-033 T012, T032.
Total: **35 tasks**. MVP = Setup + Foundational + US1.
