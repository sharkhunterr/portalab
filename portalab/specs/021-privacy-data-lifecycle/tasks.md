---
description: "Task list — Privacy, Data Lifecycle & Audit/Security completion (spec 021)"
---

# Tasks: Privacy, Data Lifecycle & Audit/Security completion

**Input**: `specs/021-privacy-data-lifecycle/` · **Branch**: `021-privacy-data-lifecycle` · **Roadmap**: Phase 1 step 3 · **Tests**: included (security-sensitive).
Abbrev: **`PV/`** = `backend/src/portalab/modules/privacy`; **`AU/`** = `backend/src/portalab/modules/authz/audit`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` kernel registry/tombstone · `D-002` participant contracts + deletion saga · `D-003` `AuditSink`, `audit.audit_entries`, `VisibilityFilter` port, `require()`.

## Phase 1: Setup
- [ ] T001 Create `PV/{visibility,policies,retention,participants,aggregation,purge,api,models}/__init__.py`, `AU/`, `backend/migrations/privacy/versions/`, `backend/tests/{unit,integration,security}/privacy/`
- [ ] T002 [P] Declare settings `privacy.minAggregateSize` (default 5), `privacy.retention.<class>.days`, `privacy.retention.auditMonths`, `privacy.exportTtlDays`, `privacy.defaultLevel.<class>`, `security.rateLimit.*`, `security.maxBodyBytes` in `PV/settings.py`
- [ ] T003 [P] Declare permissions `privacy.manage` (sensitive), `audit.read`, `services.purge` (sensitive, requires_confirmation) via `declare_permission` in `PV/permissions.py`

## Phase 2: Foundational (data + guards)
### Tests first
- [ ] T004 [P] Write `backend/tests/integration/privacy/test_schema.py`: `visibility_policies` partial unique index (one active per subject+class); `retention_runs` and `audit_checkpoints` append-only
- [ ] T005 [P] Write `backend/tests/boundary/test_classification.py`: every mutable table with PII-class columns is classified; **append-only tables contain no PII-class columns**; retention targets never include `integrity_necessary` tables
### Implementation
- [ ] T006 Implement models + Alembic revision for `visibility_policies`, `retention_runs`, `audit_checkpoints` (`PV/models/`, `backend/migrations/privacy/versions/<date>_privacy_initial.py`)
- [ ] T007 Implement the data-class enum and the `RetentionTarget` registry (`register_retention_target`) in `PV/retention/registry.py`

## Phase 3: US1 — Visibility independent of permission (P1) 🎯 MVP
### Tests first
- [ ] T008 [P] [US1] Write `backend/tests/unit/privacy/test_visibility_levels.py`: matrix over levels (public/community/leaderboards-only/private) × viewer relationship; default level used when no provider; never public by default
- [ ] T009 [P] [US1] Write `backend/tests/integration/privacy/test_permission_vs_privacy.py`: a high-permission viewer cannot read another user's Private field; filter applied after `require()`
### Implementation
- [ ] T010 [US1] Define the `VisibilityPreferenceProvider` capability contract in `backend/src/portalab/capabilities/visibility.py` and implement the identity profile-field provider adapter in `PV/visibility/providers.py`
- [ ] T011 [US1] Implement `PV/visibility/service.py` (`effective_level`: active policy ▸ preference ▸ class default) and `PV/visibility/filter.py` implementing the 003 `VisibilityFilter` port; register it replacing the pass-through default

## Phase 4: US2 — Admin override preserves and restores preference (P1)
- [ ] T012 [P] [US2] Write `backend/tests/integration/privacy/test_override_restore.py`: apply policy ⇒ effective level forced while preference row is byte-identical; user changes preference during override ⇒ stored, not effective; remove policy ⇒ preference effective again automatically; no stacking (second apply for same subject+class refused); both actions audited
- [ ] T013 [US2] Implement `PV/policies/service.py` (`apply`, `remove`, `ends_at` expiry evaluated at read time) with `AuditSink` records and `privacy.override_applied|removed` events
- [ ] T014 [US2] Implement routers `GET|POST /privacy/policies`, `DELETE /privacy/policies/{id}` in `PV/api/policies.py` guarded by `privacy.manage` (sensitive, confirmation)

## Phase 5: US3 — Classification governs handling; audit completion (P1)
### Tests first
- [ ] T015 [P] [US3] Write `backend/tests/integration/audit/test_partitions.py`: entries land in the right monthly partition; dropping an old partition via the maintenance role works; row-level UPDATE/DELETE still rejected
- [ ] T016 [P] [US3] Write `backend/tests/integration/audit/test_checkpoints_verify.py`: checkpoints chain correctly; `audit verify` passes; modifying/removing a row (superuser in test) makes verification fail and emits `audit.verification_failed`
- [ ] T017 [P] [US3] Write `backend/tests/security/audit/test_audit_query.py`: `audit.read` required; Support-level viewers get redacted context, Admin full; every read is itself audited; export honors filters
### Implementation
- [ ] T018 [US3] Add the expand/contract migration converting `audit.audit_entries` to monthly range partitions (create partitioned table, copy, swap, keep trigger) in `backend/migrations/audit/versions/<date>_audit_partitioned.py`
- [ ] T019 [US3] Implement `AU/partitions.py` (create next partitions ahead of time, retention drop by `privacy.retention.auditMonths`) and the job `audit_partition_maintenance`
- [ ] T020 [US3] Implement `AU/checkpoints.py` (batch hash chained to the previous checkpoint) + job `audit_checkpoint`, and `AU/verify.py` + CLI `portalab audit verify` in `backend/src/portalab/app/cli.py`
- [ ] T021 [US3] Implement `AU/query.py` and routers `GET /audit`, `GET /audit/export` (cursor pagination, allow-listed filters, level-based redaction, audited reads)

## Phase 6: US4/US5 — Export and deletion semantics (P1)
- [ ] T022 [P] [US5] Write `backend/tests/integration/privacy/test_registry_erasure.py`: generic participant nulls only classified columns for the user, keeps ids/FKs, idempotent; append-only integrity tables untouched
- [ ] T023 [P] [US4] Write `backend/tests/integration/privacy/test_registry_export.py`: export includes the user's classified rows, excludes secrets and other users' data
- [ ] T024 [US5] Implement `PV/participants/registry_erasure.py` (`RegistryErasureParticipant`) and `PV/participants/registry_export.py` using the kernel PII registry; register them with the capability registry for models that opt in
- [ ] T025 [US5] Ensure the deletion saga (002) invokes them and add the Coin-destruction hook point doc/test stub `backend/tests/integration/privacy/test_saga_participants_contract.py`

## Phase 7: US6 — Retention without breaking integrity (P2)
- [ ] T026 [P] [US6] Write `backend/tests/integration/privacy/test_retention.py`: delete/anonymize/aggregate/drop_partition actions per target; `integrity_necessary` never touched; run recorded in `retention_runs`; private data never exposed
- [ ] T027 [US6] Implement `PV/retention/engine.py` (batched runs, per-target error isolation) and job `retention_run` using config policies

## Phase 8: US7 — Source of truth, disconnection, external deletion (P1)
- [ ] T028 [P] [US7] Write `backend/tests/integration/privacy/test_service_purge.py`: disconnect never purges; purge requires `services.purge` + confirmation; purge job removes only that service's historized rows; audited; `service.data_purged` emitted
- [ ] T029 [US7] Implement `PV/purge/service.py`, job `purge_service_data`, and router `POST /services/{id}/purge` (uses a connectors capability to enumerate that service's data; stub until spec 005)

## Phase 9: US8 — Aggregates (P2)
- [ ] T030 [P] [US8] Write `backend/tests/unit/privacy/test_aggregation_guard.py`: cells below threshold suppressed; threshold from config; no individual reconstruction via complementary cells
- [ ] T031 [US8] Implement `PV/aggregation/guard.py` and export it as a capability for Statistics (017)

## Phase 10: Security hardening baseline & polish
- [ ] T032 [P] Write `backend/tests/security/test_headers_limits.py`: CSP, HSTS, `X-Content-Type-Options`, frame-ancestors, body-size cap (413), rate limit (429) per IP and per user, health endpoints exempt
- [ ] T033 Implement `backend/src/portalab/app/security.py` (headers, size limit, in-process rate limiter configurable via settings) and wire into the app factory
- [ ] T034 [P] Extend `.gitlab-ci.yml` `validate` with `pip-audit`, `npm audit --omit=dev`, secret scanning and fail on high severity
- [ ] T035 [P] Add observability (`PV/observability.py`): visibility decisions, active overrides, retention rows, checkpoint lag, verification status; test no PII in logs
- [ ] T036 [P] Add admin UI screens (policies, audit viewer) in `frontend/src/features/privacy/` with loading/error/unauthorized states, keyboard, axe, externalized strings
## Privacy center (user journey "Profile / Data Center → inspect data → visibility/preferences → export/delete")
- [ ] T037 [P] [US1] Write `backend/tests/integration/privacy/test_privacy_center.py`: `GET /me/privacy` lists the datum classes held about me (owner module, classification, current visibility level, policy lock, retention) and links export/deletion (002); `PUT /me/privacy/visibility/{datum_class}` changes my preference within admin policy; under an admin override the stored preference is kept and restored when the override ends (CD-016)
- [ ] T038 [US1] Implement `PV/center/service.py` + routers `GET /me/privacy`, `PUT /me/privacy/visibility/{datum_class}` (preferences stored as user-tier settings `privacy.visibility.<datum_class>` in 020, read by `VisibilityPreferenceProvider`), and frontend `frontend/src/features/privacy/PrivacyCenter.tsx` (inventory, per-datum visibility, export/delete entry points; accessible states)


## Cross-spec obligations (audit 2026-10-01 — see `decisions/PLAN_FOLLOWUPS.md`)
- [ ] T039 Expose `register_datum_class(key, owner, default_level, classification)` for modules (`progression`, `media_history`, `member_listing`, `community_activity`, `projects`, `votes`, …) and refuse plugin loads declaring personal data without an erasure participant; test `backend/tests/unit/privacy/test_datum_registry.py` (F19)

- [ ] T040 Add the migration-upgrade test (003 → privacy, audit partitioned with data) and run the full validation (`ruff`, `mypy`, `lint-imports`, suites); record results

## Dependencies & Execution Order
Setup → Foundational → **US1 (MVP)** → US2 → US3 audit completion (partition → checkpoints → query) → US4/US5 (parallel with US6/US7/US8, disjoint files) → Security/Polish. T018 must run before T019–T021. T029 uses a connectors stub until spec 005.

## Traceability (FR → tasks)
FR-001..004 T008–T011 · FR-005..008 T012–T014 · FR-009/010 T005, T015–T021 · FR-011/012 T023, T024 · FR-013..017 T022, T024, T025 · FR-018/019 T026, T027 · FR-020..022 T028, T029 · FR-023/024 T030, T031 · FR-025..027 T009, T013, T020, T021.
Spec 003 FR-034..037 (audit completion) T015–T021 · Constitution VI hardening T032–T034.
Total: **37 tasks**. MVP = Setup + Foundational + US1.
