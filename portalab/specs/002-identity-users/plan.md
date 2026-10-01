# Implementation Plan: Identity & Users

**Branch**: `002-identity-users` | **Date**: 2026-10-01 | **Spec**: `specs/002-identity-users/spec.md`
**Roadmap**: Phase 1 — SOCLE, step 2 *Auth / Users / Permissions* (with spec 003, planned next on branch `003-roles-permissions`).
**Input**: spec 002 (FR-001..036, US1..8) + approved plan of spec 001 (kernel, ports, conventions).

## Summary

Module `identity` implements the account lifecycle state machine, local authentication with server-side revocable sessions, profile/display-name/avatar, onboarding progress, user-initiated export and deletion (pending → tombstone), admin account operations (suspend/reactivate), the single-Admin **transfer orchestration**, and the first-Admin bootstrap. It **does not** own: roles/permissions and the single-Admin DB invariant (003 / `authz`), preferences storage (Administration, CD-011), visibility engine and export/erasure semantics (021), the audit store beyond the `AuditSink` port (003 introduces it), the event store (007).

## Technical Context

**Language/Version**: Python 3.12 · **Dependencies (new)**: `argon2-cffi`, `Pillow` (avatar validation), plus the 001 baseline (FastAPI, SQLAlchemy 2 async, Alembic, Pydantic 2)
**Storage**: PostgreSQL schema `identity` (see `data-model.md`); avatar/export blobs via kernel `core.blobstore` (filesystem baseline)
**Testing**: pytest on real PostgreSQL; security suite; state-machine unit tests; Vitest for the auth screens
**Target Platform**: self-hosted containers (001) · **Project Type**: module in the modular monolith
**Constraints**: non-enumerating auth; sessions revocable immediately; no secret in logs/events; all authorization server-side via `authz.authorize()`
**Scale/Scope**: personal/community scale; 8 tables; ~20 endpoints

## Constitution Check — PASS

I Product Integrity (states, invariants as specified) · II/XX no new engine: roles in `authz`, config in Administration, erasure/export via participant capabilities · III extension: `AuthProvider` + participant capabilities are extension points · V provenance n/a · VI default-deny, Argon2id, hashed tokens, CSRF · VII Privacy: tombstone via 001 registry, personal data classified · VIII tests per §10 · IX auth degrades safely (DB down ⇒ 503, never open) · XII auth screens meet WCAG 2.2 AA (forms, errors) · XIII audit via `AuditSink` · XIX expand/contract migrations. No violations; Complexity Tracking empty.

## 1. Architecture

```
HTTP ─▶ auth middleware ─▶ SessionService ─▶ Principal ─▶ routers (identity.api)
                                   │                          │
                          AuthProvider(local)         AccountService (state machine)
                                   │                          ├─ outbox: EventPublisher
                          CredentialStore (Argon2id)          ├─ AuditSink
                                                              └─ capability calls: authz.admin_authority,
Worker jobs: expire_verification · mark_inactive ·                  privacy.erasure_participant*, export_contributor*
             finalize_deletion (saga) · build_export · prune_sessions
```
Boundaries: `modules/identity` imports only `core` and `capabilities`; talks to `authz` through `authz.*` capabilities and to other modules through participant capabilities/events (001 boundary rules).

## 2. Components

| Component | Responsibility | Depends on | Key interface | Constraint | Tests |
|---|---|---|---|---|---|
| `AccountService` | state machine + guard table; one transaction per transition (state, history row, event, audit) | `core.db`, `EventPublisher`, `AuditSink` | `transition(user, to, actor, reason)` | illegal transitions raise `state_transition_forbidden`; Deleted terminal | exhaustive transition table test |
| `RegistrationService` | create `pending_verification`, issue/verify tokens, expiry | `AccountService`, notification port (010 later) | `register()`, `verify()` | policy-gated; non-enumerating | enumeration/timing tests |
| `AuthProvider` (local) + `CredentialStore` | verify password (Argon2id), rehash on param change | `core.secrets` | `authenticate()` | constant-time path for unknown login | timing test, rehash test |
| `SessionService` | create/validate/revoke sessions, idle+absolute expiry, revoke-all-for-user | `core.db` | `create()`, `resolve()`, `revoke()` | hashed token; rotation on login | fixation, expiry, revoke-on-suspend tests |
| `LoginThrottle` | progressive delay per (identifier, ip) | `core.db` | `check()`, `record_failure()` | never hard-locks the Admin | throttle test |
| `ProfileService` | display name rules, profile fields (visibility *preference*), avatar | `core.blobstore` | `update_profile()`, `set_avatar()` | NFKC+casefold uniqueness; re-encode images | uniqueness/avatar tests |
| `OnboardingTracker` | progress per step, completion event | `AccountService` | `complete(step)` | steps' content owned elsewhere | unit |
| `DeletionSaga` | pending → grace → finalize: revoke sessions, run all `erasure_participant`s, tombstone, release name, emit events | jobs, capability registry, kernel tombstone | `request()`, `cancel()`, `finalize()` | idempotent per participant; cancel only before `due_at`; sole Admin blocked | saga + failure-injection tests |
| `ExportBuilder` | gather `export_contributor`s into an expiring bundle | blobstore, jobs | `request()` | no secrets / other users' private data | export content test |
| `AdminTransferService` | atomic Admin handover via `authz.admin_authority`, step-up re-auth | `authz` capability | `transfer(target)` | exactly one Admin before/after | concurrency test |
| `IdentityBootstrap` | first Admin creation (CLI + callable by 020 wizard) | `AccountService` | `create_first_admin()` | refuses if Admin exists | unit/integration |
| `identity.api` | routers per `contracts/identity-contracts.md` | all above | OpenAPI | `authorize()` on every route | permission matrix tests |

## 3. Domain / Data Model
See `data-model.md`. Key rules: `display_name_key` unique & nullable; credentials separate from users; `account_state_history` append-only; tombstone keeps `id`; PII columns classified in the 001 registry.

## 4. API & Contracts
See `contracts/identity-contracts.md`. Contracts exposed: `identity.directory` (incl. `is_active_account`), `identity.principal`, `AuthProvider`, `privacy.erasure_participant`, `privacy.export_contributor`, `IdentityBootstrap`.

## 5. Events
Producer: identity → `EventPublisher` (envelope per EVENT_MODEL.md) for the 14 `user.*` events listed in `data-model.md`. Consumers in this spec: none beyond its own jobs. Identity/idempotency: event id = UUIDv7; dedup key for state-change events = `(user_id, to_state, transition_seq)` so replays never double-apply (CD-012 form finalized by 007). Ordering: per-user order via `transition_seq`. Persistence: history table now; 007 store later. Failure: outbox retry; consumers idempotent.

## 6. Permissions & Security
| Operation | Actor | Permission | Scope | Audit |
|---|---|---|---|---|
| view/edit own profile, avatar, export, request/cancel deletion | user | `users.self.manage` | self | deletion/export audited |
| view another profile | user | `users.read` + visibility (021) | target field set | no |
| suspend/reactivate/force deletion | Admin | `users.manage` | any non-Admin | yes, confirmation |
| Admin transfer | Admin | `users.admin.transfer` + step-up auth | global | yes, sensitive |
Failed authentication recorded (hashed identifier, ip prefix) via `AuditSink`. Sole Admin cannot be deleted/suspended/demoted except through transfer. Sessions: `__Host-` cookie, HttpOnly, Secure, SameSite=Lax, CSRF header, rotation on login/privilege change.

## 7. Configuration (declared into Administration, CD-011)
`identity.sessionIdleMinutes`, `identity.sessionAbsoluteHours`, `identity.verificationTtlHours`, `identity.deletionGraceDays`, `identity.dormancyDays`, `identity.registrationMode`, `identity.passwordPolicy`, `identity.argon2Params`. Declared with code defaults now; values resolved by the Configuration step.

## 8. External Integrations
None required. Verification delivery uses a `VerificationChannel` port (email via Notifications 010 later; until then administrator-visible token — see risk R2).

## 9. Error Handling & Resilience
DB down ⇒ auth fails closed (503), never open · unknown/invalid cookie ⇒ anonymous (401 on protected routes) · participant failure during deletion ⇒ saga retries that participant, deletion not finalized until all succeed (visible to Observability) · avatar processing failure ⇒ 422, old avatar kept · duplicate request ⇒ idempotency key on register/deletion/export · clock skew ⇒ expiry compared server-side only.

## 10. Observability
Structured logs (no identifiers in clear), counters: logins ok/failed/throttled, state transitions by type, saga step failures, session revocations. Feeds Observability (025) later via the kernel metrics hooks.

## 11. Testing Strategy
Unit: transition table, display-name normalization, password-policy. Integration (real PG): register→verify→login→logout; suspension revokes sessions; deletion saga with a fake participant failing once; export bundle contents; sole-Admin protection incl. concurrent transfer. Security: enumeration (status+body+timing), CSRF, cookie flags, session fixation, throttling, token hashing at rest, secrets absent from logs/events. Permission matrix generated from route table. Migration: upgrade from empty + from 001 baseline. UI: auth forms states (loading/error/unauthorized), a11y with axe.

## 12. Migration / Versioning
Alembic revision set for schema `identity` (expand/contract); `account_state_history` append-only trigger via 001 helper; API under `/api/v1`; capability contracts semver'd.

## 13. Cross-Spec Dependencies
- **Prerequisites**: 001 kernel (db, errors, jobs, secrets, blobstore additions, settings declaration, privacy registry, tombstone); **003** (`authorize`, `authz.admin_authority`, `AuditSink`) — planned next, implemented together in step 2.
- **Exposes to**: 003 (users FK), every module (`identity.principal`, `identity.directory`), 012 voting (`is_active_account`), 013 (erasure participant for Coins), 020 (bootstrap + preferences facade), 021 (erasure/export engine), 018/019 (acting principal).
- **Independent**: state machine, credential store, display-name rules.
- **After this**: Configuration (user-tier preferences, `/me/preferences`), Events (007 adopts the envelope), Notifications (verification delivery).

## 14. Implementation Phases
1. **Data & state machine** (tables, migrations, `AccountService`, history/audit/event writing).
2. **Authentication** (credentials, sessions, throttle, middleware, `Principal`).
3. **Registration/verification & bootstrap CLI**.
4. **Profile, display name, avatar, onboarding tracker**.
5. **Lifecycle jobs** (verification expiry, dormancy, session pruning).
6. **Deletion saga + export builder** (participant capabilities).
7. **Admin operations & transfer**.
8. **API, auth UI screens, security hardening & test suite**.

## 15. Technical Decisions & Trade-offs
See `research.md` R1–R14. Notable: sessions over JWT (immediate revocation), throttle over lockout (Admin safety), participant capabilities over hard-coded deletion list, preferences deferred to Administration to avoid a second config store.

## 16. Risks / Open Technical Questions
- **R1 Registration policy not specified** (open/invite/approval): plan makes it a config value `identity.registrationMode` with default `invite_only` (fits CD-025 personal portal). **Product confirmation needed.**
- **R2 Verification channel** needs email (Notifications 010, later phase): baseline = admin-visible one-time token; fits `VerificationChannel` port.
- **R3 Privacy (021) is not an explicit roadmap step**: export/erasure semantics are consumed here through participant capabilities with kernel baseline; 021 is planned inside the "Audit / Security" step.
- **R4** MFA/OIDC absent from spec ⇒ only the port exists.
- **R5** Preference endpoints depend on the Configuration step; until then `FR-013/014/015/017` are *declared, not served*.
- **R6** `core.blobstore` and `EventPublisher` are small kernel additions first required here (flagged for 001 maintainers).

## Project Structure
```text
specs/002-identity-users/ spec.md plan.md research.md data-model.md quickstart.md contracts/ tasks.md
backend/src/portalab/modules/identity/{domain,services,api,jobs,models}/ · migrations/identity/versions/
frontend/src/features/auth/ (login, verify, account screens)
```
