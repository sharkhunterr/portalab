---
description: "Task list — Events & History (spec 007)"
---

# Tasks: Events & History

**Input**: `specs/007-events-history/` · **Branch**: `007-events-history` · **Roadmap**: Phase 2 step 5 · **Tests**: included.
Abbrev: **`EV/`** = `backend/src/portalab/modules/events`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` jobs/db · `D-003` authz+audit · `D-020` config · `D-021` partition helper, retention registry, `VisibilityFilter`.

## Phase 1: Setup
- [ ] T001 Create `EV/{registry,publisher,dedup,quarantine,consumers,history,replay,api,models}/__init__.py`, `backend/migrations/events/versions/`, `backend/tests/{unit,integration,contract,security}/events/`
- [ ] T002 [P] Declare settings `events.dispatchBatchSize`, `events.maxDeliveryAttempts`, `events.retryBackoff`, `events.retention.business.months`, `events.retention.technical.days`, `events.dedupKeyRetention`, `events.deadLetterAlertThreshold` in `EV/settings.py`
- [ ] T003 [P] Declare permissions `events.manage` (sensitive), `events.replay` (sensitive, requires_confirmation) in `EV/permissions.py`

## Phase 2: Foundational
### Tests first
- [ ] T004 [P] Write `backend/tests/integration/events/test_schema.py`: partitioned `events.events` accepts inserts per month, rejects UPDATE/DELETE, unique (type, dedup_key) in `dedup_keys`, unique (consumer, event_id) in `deliveries`
- [ ] T005 [P] Write `backend/tests/unit/events/test_registry.py`: schema validation, PII/secret-classified field rejected, version declared, duplicate type rejected
### Implementation
- [ ] T006 Implement models + Alembic revision for all `events.*` tables (partition creation via the 021 helper)
- [ ] T007 Implement `EV/registry/types.py` (`EventType`, `register_event_type`, validation of payload schema against the PII/secret registry)

## Phase 3: US3 — Idempotent ingestion and deduplication (P1) 🎯 MVP
### Tests first
- [ ] T008 [P] [US3] Write `backend/tests/unit/events/test_dedup_keys.py`: reliable source id wins; otherwise deterministic composite of declared fields; two events differing only by timestamp are **not** collapsed; same logical occurrence redelivered later is
- [ ] T009 [P] [US3] Write `backend/tests/integration/events/test_publish_atomic.py`: event and caller state commit/rollback together; concurrent duplicate publishes yield exactly one stored event; `occurred_at` vs `received_at` preserved, `received_at` never used as identity
### Implementation
- [ ] T010 [US3] Implement `EV/dedup/keys.py` (strategies from the registry) and `EV/dedup/service.py` (`dedup_keys` insert-or-detect)
- [ ] T011 [US3] Implement `EV/publisher/publisher.py` as the real `EventPublisher` (kernel port from 002) and switch the app composition to it; keep a contract test proving 002/003/020/021 emissions still validate
- [ ] T012 [US3] Implement `EV/quarantine/service.py` + tests `backend/tests/integration/events/test_quarantine.py` (unknown type, invalid payload, unsupported version ⇒ quarantine, not history)

## Phase 4: US1/US4 — Fan-out to independent consumers (P1)
### Tests first
- [ ] T013 [P] [US1] Write `backend/tests/integration/events/test_fanout_isolation.py`: one event reaches several consumers independently; a failing consumer retries then dead-letters while others advance; producer never waits; adding a consumer needs no producer change
- [ ] T014 [P] [US4] Write `backend/tests/integration/events/test_consumer_idempotence.py`: redelivery after crash applies `idempotent_effect(key)` once; offsets resume after dispatcher restart
### Implementation
- [ ] T015 [US4] Implement `EV/consumers/runtime.py` (`@consumer`, cursors, deliveries, retry/backoff, dead letter, `ctx.idempotent_effect`) on top of `core.jobs`
- [ ] T016 [US4] Implement `EV/consumers/dispatcher.py` (batch by `seq`, per-consumer jobs) and the dead-letter event `events.consumer_dead_lettered`
- [ ] T017 [US1] Build the consumer contract test kit `backend/tests/contract/consumer_kit.py` reusable by every later module (duplicate delivery, crash, replay flag)

## Phase 5: US2 — Event shape and versioning (P1)
- [ ] T018 [P] [US2] Write `backend/tests/unit/events/test_envelope_versions.py`: envelope fields complete (id, type, occurred_at, received_at, source, actor, object, metadata, version); new version leaves old events untouched; upcaster applied for consumers declaring older support
- [ ] T019 [US2] Implement upcaster registry in `EV/registry/upcasters.py` and envelope validation in `EV/publisher/envelope.py`

## Phase 6: US5 — History with provenance and visibility (P1)
- [ ] T020 [P] [US5] Write `backend/tests/integration/events/test_history_privacy.py`: owner sees own history; another permitted user sees nothing private; disconnected-service events remain; admin payload view redacted by level
- [ ] T021 [US5] Implement `EV/history/query.py` (`for_user`, `for_subject`, cursor pagination ordered `(occurred_at, event_id)`) passing results through `require()` and `VisibilityFilter`
- [ ] T022 [US5] Add routers `GET /me/history`, `GET /subjects/{type}/{id}/history`, `GET /admin/events`, `/admin/events/deliveries`, `/admin/events/quarantine`, quarantine release/discard in `EV/api/`

## Phase 7: US6/US7 — Retention and audit relation (P2)
- [ ] T023 [P] [US6] Write `backend/tests/integration/events/test_retention.py`: partitions dropped per class windows; `dedup_keys`/`deliveries` pruned consistently; business events outlive technical ones
- [ ] T024 [US6] Register retention targets (events by class, dedup keys, deliveries) with the 021 engine in `EV/retention.py`
- [ ] T025 [P] [US7] Write `backend/tests/integration/events/test_audit_link.py`: a sensitive action produces one event and one audit entry sharing `event_id`/correlation; audit remains in its own table
- [ ] T026 [US7] Add the `event_id` correlation column migration for `audit.audit_entries` and write it from the engine/AuditSink path

## Phase 8: US8 — Reconstruction without side effects (P2)
- [ ] T027 [P] [US8] Write `backend/tests/integration/events/test_replay.py`: projection rebuilt deterministically in order; `replay=True` suppresses non-replay-safe handlers; originals unmodified; rule version looked up with `as_of=occurred_at`
- [ ] T028 [US8] Implement `EV/replay/service.py`, `replay_runs` handling, router `POST /admin/replay` (confirmation, audited) and CLI `portalab events replay`

## Phase 9: Polish & validation
- [ ] T029 [P] Add SSE subscriber for the 001 stream endpoint in `EV/consumers/sse.py` (permission-filtered) with test `backend/tests/integration/events/test_sse_filter.py`
- [ ] T030 [P] Add observability in `EV/observability.py`: consumer lag, failures, dead letters, ingestion accepted/duplicate/quarantined; test no PII in logs
- [ ] T031 [P] Admin UI in `frontend/src/features/admin/events/` (deliveries, dead letters, quarantine, replay) with loading/error/unauthorized, keyboard, axe, externalized strings

## Cross-spec obligations (audit 2026-10-01 — see `decisions/PLAN_FOLLOWUPS.md`)
- [ ] T032 Extend the event-type registry in `EV/registry/` with per-field annotations `rewardable` (013) and `aggregatable` (017), a per-type `automatable` flag (019), the `provenance.automation{id, execution_id, depth}` convention and `actor_kind` values `ai|automation`; test `backend/tests/unit/events/test_registry_annotations.py` (F2)
- [ ] T033 [P] Expose owner-tagged registration on the event-type registry: `register(..., owner="module:<id>|plugin:<key>")` and `unregister(owner)`, with a test in `backend/tests/unit/events/test_registry_owner.py` proving all contributions of an owner disappear (required by 023's conformance sweep, F20)

- [ ] T034 Permission-matrix test for all events routes `backend/tests/security/events/test_permission_matrix.py` and migration-upgrade test (020 → events); run full validation and record results

## Dependencies & Execution Order
Setup → Foundational → **US3 (MVP)** → US1/US4 consumers → US2 → US5 history → US6/US7 → US8 → Polish. T011 swaps the publisher implementation (contract test guards earlier modules).

## Traceability (FR → tasks)
FR-001..004 T007, T018, T019 · FR-005..009 T013–T017 · FR-010..014 T008–T012 · FR-015..020 T020–T022, T026 · FR-021/022 T023, T024 · FR-023/024 T025, T026 · FR-025/026 T008, T010 · FR-027..030 T027, T028 · FR-031 T030.
Total: **32 tasks**. MVP = Setup + Foundational + US3.
