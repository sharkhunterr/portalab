---
description: "Task list — Identity & Users (spec 002)"
---

# Tasks: Identity & Users

**Input**: `specs/002-identity-users/` plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**Branch**: `002-identity-users` · **Roadmap**: Phase 1 step 2 · **Tests**: included (plan §11, security-sensitive).
**Cross-spec prerequisites (not implemented here)**: `D-001` kernel from spec 001 (db, errors, jobs, secrets, settings declaration, privacy registry, tombstone); `D-003` spec 003 provides `authorize()`, `authz.admin_authority`, `AuditSink` — until it lands, tests use in-memory stubs of those ports. Commit trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Paths relative to repo root `portalab/`; `backend/src/portalab/modules/identity` abbreviated **`IDN/`**.

## Scope note
FR-013/014/015/017 (preferences) and the preference half of FR-016 are **declared, not served** here: user-tier values belong to the Administration configuration system (Configuration step). FR-018/019/022–024 are delivered through participant capabilities whose engine semantics are owned by Privacy (021).

## Phase 1: Setup
- [ ] T001 Create package skeleton `IDN/{domain,services,api,jobs,models}/__init__.py`, `backend/migrations/identity/versions/`, `backend/tests/{unit,integration,security}/identity/`, `frontend/src/features/auth/`
- [ ] T002 Add `argon2-cffi` and `Pillow` to `backend/pyproject.toml` (+ `uv.lock`), allow them in importlinter only for `modules.identity`
- [ ] T003 [P] Declare the settings `identity.sessionIdleMinutes`, `identity.sessionAbsoluteHours`, `identity.verificationTtlHours`, `identity.deletionGraceDays`, `identity.dormancyDays`, `identity.registrationMode` (default `invite_only`), `identity.passwordPolicy`, `identity.argon2Params` via the kernel `declare_setting` in `IDN/settings.py`
- [ ] T004 [P] Add the kernel `EventPublisher` port + outbox adapter in `backend/src/portalab/core/event_port.py` (envelope fields per EVENT_MODEL.md: event_id, type, occurred_at, received_at, source, actor, object, metadata, version)
- [ ] T005 [P] Add the kernel `BlobStore` port + filesystem implementation (content-addressed keys, delete, stream) in `backend/src/portalab/core/blobstore.py` with a unit test `backend/tests/unit/test_blobstore.py`
- [ ] T006 [P] Add in-memory test doubles for `Authorizer`, `AuditSink`, capability registry in `backend/tests/identity_fakes.py` (replaced by real 003 implementations when available)

## Phase 2: Foundational (blocking)
### Tests first
- [ ] T007 [P] Write `backend/tests/unit/identity/test_state_machine.py`: exhaustive allowed/forbidden transition table from spec 002 (incl. Pending Deletion → prior state, Deleted terminal)
- [ ] T008 [P] Write `backend/tests/unit/identity/test_display_name.py`: NFKC+casefold key, homoglyph/case collisions rejected, validation limits
- [ ] T009 [P] Write `backend/tests/integration/identity/test_schema.py`: migration creates the `identity` tables, partial unique indexes, `account_state_history` rejects UPDATE/DELETE
### Implementation
- [ ] T010 Implement SQLAlchemy models in `IDN/models/` for `users`, `credentials`, `sessions`, `login_throttle`, `verification_tokens`, `profiles`, `profile_fields`, `account_state_history`, `deletion_requests`, `onboarding_progress`, `export_jobs` per `data-model.md`; register PII classes in the privacy registry
- [ ] T011 Create the Alembic revision `backend/migrations/identity/versions/<date>_identity_initial.py` (tables, CHECK on `state`, unique/partial indexes, append-only trigger on history)
- [ ] T012 Implement `IDN/domain/state_machine.py`: states, guard table, `transition_seq`, domain errors (`state_transition_forbidden`)
- [ ] T013 Implement `IDN/domain/display_name.py`: normalization key + validation
- [ ] T014 Implement `IDN/services/account_service.py`: single-transaction transition (state row, history row, outbox event, `AuditSink` record) using T012
- [ ] T015 Implement the `identity.directory` capability (`get_user_summary`, `is_active_account`, `exists`) in `IDN/services/directory.py` and register it in the capability registry

## Phase 3: US2 — Authenticate and manage a session (P1) 🎯 MVP
**Independent test**: valid login for an Active account creates a revocable session; invalid/unavailable accounts get an indistinguishable denial; logout revokes.
### Tests first
- [ ] T016 [P] [US2] Write `backend/tests/security/identity/test_login_enumeration.py`: unknown login, wrong password, non-active account ⇒ identical status/body/shape; timing within tolerance of the real path
- [ ] T017 [P] [US2] Write `backend/tests/security/identity/test_session_cookie_csrf.py`: cookie flags (`__Host-`, HttpOnly, Secure, SameSite=Lax), CSRF header required on unsafe methods, session rotation on login (fixation)
- [ ] T018 [P] [US2] Write `backend/tests/integration/identity/test_sessions.py`: idle/absolute expiry, `revoke_all(user)`, token stored only as hash
- [ ] T019 [P] [US2] Write `backend/tests/security/identity/test_throttle.py`: progressive delay per (identifier, ip), the Admin is never hard-locked
### Implementation
- [ ] T020 [US2] Implement `IDN/services/credentials.py` (Argon2id hash/verify, rehash-on-login, constant-time dummy verification for unknown logins)
- [ ] T021 [US2] Implement `IDN/services/sessions.py` (create/resolve/revoke, hashed token, expiry from settings, rotation)
- [ ] T022 [P] [US2] Implement `IDN/services/throttle.py` (hashed key, window, progressive `blocked_until`)
- [ ] T023 [US2] Implement the `AuthProvider` port and the local provider in `IDN/services/auth.py`; record failed attempts through `AuditSink` (hashed identifier, ip prefix) and publish `user.signed_in`/`user.signed_out`
- [ ] T024 [US2] Implement the auth middleware producing `Principal` (`identity.principal`) in `IDN/api/middleware.py` and wire it into the 001 app factory with CSRF check
- [ ] T025 [US2] Implement routers `POST /auth/login`, `POST /auth/logout`, `GET /me` in `IDN/api/auth.py` with problem+json codes `auth.invalid_credentials` / `auth.account_unavailable`

## Phase 4: US1 — Create an account and complete onboarding (P1)
**Independent test**: register → verify → Active with onboarding started; second registration with the same display name is rejected; bootstrap creates the sole Admin once.
### Tests first
- [ ] T026 [P] [US1] Write `backend/tests/integration/identity/test_registration.py`: policy-gated register, non-enumerating response, token expiry, verify → `active` + `user.verified`/`user.created` events
- [ ] T027 [P] [US1] Write `backend/tests/integration/identity/test_bootstrap.py`: `create_first_admin` succeeds once, refuses when an Admin exists (concurrent calls ⇒ one winner)
### Implementation
- [ ] T028 [US1] Implement `IDN/services/registration.py` (`register`, `verify`, token issue/hash/expiry, `VerificationChannel` port with an admin-visible baseline channel)
- [ ] T029 [US1] Implement `IDN/services/onboarding.py` (progress rows, completion event; step content owned by other modules)
- [ ] T030 [US1] Implement `IDN/services/bootstrap.py` and CLI command `portalab admin bootstrap` in `backend/src/portalab/app/cli.py` (calls `authz.admin_authority` to grant Admin)
- [ ] T031 [US1] Add routers `POST /auth/register`, `POST /auth/verify` in `IDN/api/auth.py` honoring `identity.registrationMode`
- [ ] T032 [P] [US1] Implement the lifecycle job `verification_expiry` in `IDN/jobs/verification_expiry.py` (Pending Verification → Pending Deletion/Deleted per policy)

## Phase 5: US7 — Active / inactive / suspended (P2)
- [ ] T033 [P] [US7] Write `backend/tests/integration/identity/test_suspension.py`: suspend revokes sessions and blocks login; reactivate restores; both audited and evented
- [ ] T034 [US7] Implement `IDN/services/admin_ops.py` (`suspend`, `reactivate`) enforcing `users.manage` and sole-Admin protection
- [ ] T035 [US7] Implement the job `mark_inactive` in `IDN/jobs/dormancy.py` (Active ⇄ Inactive by `identity.dormancyDays`, data preserved) and routers `GET /users`, `POST /users/{id}/suspend|reactivate` in `IDN/api/admin.py`

## Phase 6: US3 — Profile, avatar, display name (P2)
- [ ] T036 [P] [US3] Write `backend/tests/integration/identity/test_profile.py`: unique display name conflict ⇒ `user.display_name_taken`; field visibility *preference* stored; avatar replace leaves no reachable old blob
- [ ] T037 [P] [US3] Write `backend/tests/unit/identity/test_avatar_validation.py`: type/size/dimension limits, metadata stripped, undecodable file rejected
- [ ] T038 [US3] Implement `IDN/services/profile.py` and `IDN/services/avatar.py` (Pillow decode/re-encode, blobstore, old-blob deletion job)
- [ ] T039 [US3] Add routers `PATCH /me/profile`, `PUT|DELETE /me/avatar`, `GET /users/{id}/profile` (visibility filtering delegated to the 021 port; default not-public) in `IDN/api/profile.py`

## Phase 7: US6 — Deletion lifecycle (P1)
**Independent test**: request → pending (sessions revoked), cancel restores prior state; after `due_at` the saga tombstones the user while ledger/history rows keep the same `id`.
- [ ] T040 [P] [US6] Write `backend/tests/integration/identity/test_deletion_saga.py`: cancel before due; finalize runs every registered participant (one failing once, retried); tombstone nulls PII, keeps id; name key released; sole Admin refused
- [ ] T041 [P] [US6] Write `backend/tests/integration/identity/test_export.py`: bundle contains the user's contributor records, never credentials/tokens/other users' private data; expires
- [ ] T042 [US6] Define the `privacy.erasure_participant` and `privacy.export_contributor` capability contracts in `backend/src/portalab/capabilities/privacy_participants.py`
- [ ] T043 [US6] Implement `IDN/services/deletion.py` (request/cancel/finalize saga, per-participant state in `deletion_requests.saga_state`, step-up re-auth) and the job `finalize_deletion` in `IDN/jobs/finalize_deletion.py`
- [ ] T044 [US6] Register identity's own erasure participant (credentials, sessions, verification tokens, avatar blob, profile fields) and export contributor in `IDN/services/participants.py`
- [ ] T045 [US6] Implement `IDN/services/export.py` + job `build_export` and routers `POST /me/deletion`, `DELETE /me/deletion`, `POST /me/export`, `GET /me/export/{id}` in `IDN/api/lifecycle.py`

## Phase 8: US8 — Roles and the single-Admin guarantee (P1)
- [ ] T046 [P] [US8] Write `backend/tests/integration/identity/test_admin_transfer.py`: transfer leaves exactly one Admin before/after; concurrent transfers ⇒ one winner; requires step-up re-auth; never zero Admins; second-Admin/delegation attempts refused
- [ ] T047 [US8] Implement `IDN/services/admin_transfer.py` calling `authz.admin_authority` atomically, emitting `user.admin_transferred` and an audit record; router `POST /admin/transfer`
- [ ] T048 [US8] Implement the `identity.principal` ↔ roles reference (roles resolved by `authz`, not stored here) and the generated permission-matrix test `backend/tests/security/identity/test_permission_matrix.py` over all identity routes (deny-by-default)

## Phase 9: Polish & validation
- [ ] T049 [P] Build the auth UI in `frontend/src/features/auth/` (login, verify, account/profile, deletion/export screens) with loading/error/unauthorized states, keyboard/focus, axe tests, strings externalized for i18n
- [ ] T050 [P] Add logging/metrics for logins, throttles, transitions, saga step failures in `IDN/observability.py` (no identifiers in clear); test `backend/tests/security/identity/test_no_secrets_in_logs.py`
- [ ] T051 Add the migration-upgrade test (001 baseline → identity) and run the full suite + `ruff`, `mypy`, `lint-imports`, record results

## Dependencies & Execution Order
Setup → Foundational (T007–T015) → **US2 (MVP)** → US1 → US7 → US3 / US6 (parallel) → US8 → Polish. US6 needs T042 before T043/T044; US8 needs spec 003's `authz.admin_authority` (stub until then). US3 and US6 touch disjoint files and can run in parallel.

## Traceability (FR → tasks)
FR-001/003/004 T012–T015 · FR-002/016 T028–T031 · FR-005..008 T016–T025 · FR-009..012 T036–T039 · FR-013..015,017 declared T003 (served by Configuration step) · FR-018/019 T041,T044,T045 · FR-020..026 T040–T045 · FR-027..031 T046–T048 · FR-032/033 T033–T035 · FR-034..036 T014, T023, T050.
Total: **51 tasks**. MVP = Setup + Foundational + US2.
