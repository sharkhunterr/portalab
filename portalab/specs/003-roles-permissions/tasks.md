---
description: "Task list — Roles, Permissions & Authorization (spec 003)"
---

# Tasks: Roles, Permissions & Authorization

**Input**: `specs/003-roles-permissions/` · **Branch**: `003-roles-permissions` · **Roadmap**: Phase 1 step 2 (implemented together with spec 002; **identity tables (002 T010–T011) must exist first**) · **Tests**: included.
Abbreviation: **`AZ/`** = `backend/src/portalab/modules/authz`. Commit trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisite `D-001`: kernel (db, errors, jobs, secrets, `EventPublisher` from 002 T004). This list also delivers the `AuditSink` and minimal audit model; the **Audit/Security** step completes them.

## Phase 1: Setup
- [X] T001 Create `AZ/{catalog,grants,engine,admin_authority,audit,confirmation,api,models}/__init__.py`, `backend/migrations/{authz,audit}/versions/`, `backend/tests/{unit,integration,security}/authz/`
- [X] T002 [P] Add the shared test fixtures `backend/tests/authz_fixtures.py` (users, roles, grants, principals incl. `channel=ai|automation|plugin`)
- [X] T003 [P] Declare settings `authz.confirmationTtlSeconds`, `authz.auditContextMaxBytes` through the kernel `declare_setting` in `AZ/settings.py`

## Phase 2: Foundational (data)
### Tests first
- [X] T004 [P] Write `backend/tests/integration/authz/test_schema.py`: tables exist; partial unique index allows at most one active `admin` assignment; reserved-permission trigger rejects grants to non-admin holders; `audit.audit_entries` rejects UPDATE/DELETE
### Implementation
- [X] T005 Implement SQLAlchemy models `AZ/models/` for `permissions`, `roles`, `groups`, `grants`, `user_roles`, `user_groups`, `admin_singleton`, `confirmations`, and `audit_entries` per `data-model.md`; classify PII (none expected) in the privacy registry
- [X] T006 Create Alembic revisions `backend/migrations/authz/versions/<date>_authz_initial.py` and `backend/migrations/audit/versions/<date>_audit_initial.py` (CHECKs, partial unique index, reserved-permission trigger, append-only trigger via the 001 helper, seed `admin_singleton` and base roles `user|support|moderator|editor|admin`)

## Phase 3: US6 — Permissions declared by core, modules and plugins (P2)
- [X] T007 [P] [US6] Write `backend/tests/integration/authz/test_catalog.py`: `declare_permission` idempotent upsert; reserved metadata; plugin disable ⇒ permissions inactive and not granting; re-enable restores
- [X] T008 [US6] Implement `AZ/catalog/declare.py` (`declare_permission(...)` registry, startup upsert, `default_roles` seeding) and `AZ/catalog/lifecycle.py` (`set_plugin_permissions_enabled(plugin_id, enabled)`)
- [X] T009 [US6] Declare the core catalog entries from the spec's illustrative list in `AZ/catalog/core_permissions.py` (`users.read|manage|self.manage|roles.manage|admin.transfer`, `services.*`, `infrastructure.read`, `ai.use`, `marketplace.manage`, `economy.manage`, `tickets.*`, `statistics.*`, `events.manage`, `automation.manage`, `security.manage`, `audit.read`, content read/create/modify/publish/delete) flagging sensitive/reserved ones
- [X] T010 [P] [US6] Add the CI test `backend/tests/boundary/test_declared_permissions.py`: every permission key referenced by a route or `require()` call is declared

## Phase 4: US1 — Deny-by-default authorization (P1) 🎯 MVP
**Independent test**: a permitted action succeeds, a non-permitted one is refused server-side regardless of the UI.
### Tests first
- [X] T011 [P] [US1] Write `backend/tests/unit/authz/test_engine.py`: default deny; union of role+group grants; explicit deny beats allow; order independence (shuffled grants ⇒ same decision); Admin = all *enabled* permissions minus denies; disabled permission never grants
- [X] T012 [P] [US1] Write `backend/tests/unit/authz/test_engine_channels.py`: principals with `channel=ai|automation|plugin` never exceed `acting_for` user's rights; unknown channel ⇒ deny
### Implementation
- [X] T013 [US1] Implement `AZ/grants/store.py` (read effective grants for a user: roles + groups, per-request memoization, no cross-request cache)
- [X] T014 [US1] Implement `AZ/engine/engine.py` (`authorize()` returning `Decision{allowed, reason, scope_matched, requires_confirmation}`, `require()` with existence-leak policy)
- [X] T015 [US1] Implement `backend/src/portalab/core/authorization.py` FastAPI dependency `require(permission, resource_resolver)` and swap it into the 001 app factory in place of the deny-everything `Authorizer` stub
- [X] T016 [P] [US1] Write `backend/tests/security/authz/test_permission_matrix.py`: generated from the app's route table — every route is protected by `require()` or explicitly allow-listed; protected routes return 401/403 without grants (replaces the 001 default-deny stub test)

## Phase 5: US4/US5 — Scopes and read/write separation (P2)
- [X] T017 [P] [US4] Write `backend/tests/unit/authz/test_scopes.py`: `self` only matches own objects; `owned` needs `owner_id`; `service:A` grant never applies to service B; module-scope grant does not cross modules
- [X] T018 [P] [US5] Write `backend/tests/unit/authz/test_read_write_separation.py`: read does not imply create/modify/publish/delete; create/modify does not imply publish
- [X] T019 [US4] Implement structural scope matching in `AZ/engine/scopes.py` (`Resource` descriptor, `self|owned|module|service|plugin|global`) and use it in T014

## Phase 6: US2 — Assign roles and groups (P1)
### Tests first
- [X] T020 [P] [US2] Write `backend/tests/integration/authz/test_assignments.py`: assign/revoke role & group changes effect on the next request; removal withdraws role-only permissions; every change emits `permission.*` events and an audit entry
- [X] T021 [P] [US2] Write `backend/tests/security/authz/test_reserved_and_escalation.py`: reserved permission cannot be granted to non-Admin role/group/plugin; a role aggregating permissions cannot reach Admin-equivalent authority; base roles undeletable
### Implementation
- [X] T022 [US2] Implement `AZ/grants/service.py` (create/patch roles & groups, grants with validation of reserved set, user role/group assignment, event publication, audit)
- [X] T023 [US2] Implement routers in `AZ/api/` for `/permissions`, `/roles`, `/groups`, grants, `/users/{id}/roles|groups`, `/me/permissions` with problem+json codes `authz.forbidden`, `authz.reserved_permission`

## Phase 7: US3 — Single-Admin authorization guarantee (P1)
- [X] T024 [P] [US3] Write `backend/tests/integration/authz/test_admin_authority.py`: first grant only when no Admin; second Admin refused; temporary/time-boxed delegation refused and audited; sole-Admin revoke without transfer refused; two concurrent transfers ⇒ exactly one succeeds, count stays 1
- [X] T025 [US3] Implement `AZ/admin_authority/service.py` (`grant_first_admin`, `transfer_admin` with `SELECT … FOR UPDATE` on `admin_singleton`, revoke/grant in one transaction, `permission.admin_transfer_attempted` event) and register the `authz.admin_authority` capability in the registry

## Phase 8: US7 — Domain permissions & sensitive actions (P2) and audit (FR-034..037)
### Tests first
- [X] T026 [P] [US7] Write `backend/tests/integration/authz/test_audit.py`: sensitive allow **and** deny produce an `audit_entries` row (actor, action, resource, scope, decision, result, correlation id); non-sensitive denials do not; UPDATE/DELETE rejected; context redacted; audit write failure ⇒ sensitive action refused (fail closed)
- [X] T027 [P] [US7] Write `backend/tests/integration/authz/test_confirmation.py`: token single-use, expires, bound to permission+resource+payload hash; replay refused
### Implementation
- [X] T028 [US7] Implement the `AuditSink` port in `backend/src/portalab/core/audit_port.py` and `AZ/audit/store.py` (append-only insert, redaction, fail-closed policy for sensitive actions); replace the in-memory double used by 002
- [X] T029 [US7] Wire audit calls into the engine for permissions flagged `sensitive` in `AZ/engine/engine.py`
- [X] T030 [US7] Implement `AZ/confirmation/service.py` (issue/consume with hashed token, TTL from settings) and expose `requires_confirmation` through `Decision`

## Phase 9: US8 — Permissions vs privacy composition (P1)
- [X] T031 [P] [US8] Write `backend/tests/integration/authz/test_privacy_composition.py`: the engine returns allow without reading visibility; a `VisibilityFilter` port applied after `require()` still hides Private data from a permitted reader; the engine never mutates visibility preferences
- [X] T032 [US8] Define the `VisibilityFilter` port (consumed from spec 021) in `backend/src/portalab/core/visibility_port.py` with a pass-through default and document the ordering "authorize → filter" in the `require()` docstring

## Phase 10: Polish & validation
- [X] T033 [P] Add metrics/logging in `AZ/observability.py` (decisions by permission, sensitive denials, audit failures, confirmations); test no secrets in logs
- [X] T034 [P] Add the migration-upgrade test (002 → authz/audit) `backend/tests/integration/authz/test_migration_upgrade.py`
- [X] T035 Add the admin UI screens for roles/groups/grants in `frontend/src/features/authz/` with loading/error/unauthorized states, keyboard operation, axe tests, externalized strings (UI hints only — server remains the authority)

## Cross-spec obligations (audit 2026-10-01 — see `decisions/PLAN_FOLLOWUPS.md`)
- [X] T036 Add `declare_permission(..., default_roles=[...])` for per-module default grants (`user|support|moderator|editor`), plugin-scoped grants `plugin:<key>.use` issued by Marketplace activation, allow-listed scoped grants for `access` products (never Admin-reserved), and principal channels `ai|automation`; tests `backend/tests/integration/authz/test_declared_defaults.py` (F15)
- [X] T037 [P] Expose owner-tagged registration on the permission catalog (plugin-declared permissions): `register(..., owner="module:<id>|plugin:<key>")` and `unregister(owner)`, with a test in `backend/tests/unit/authz/test_registry_owner.py` proving all contributions of an owner disappear (required by 023's conformance sweep, F20)

- [X] T038 Run the full validation (`ruff`, `mypy`, `lint-imports`, backend + frontend suites) and record results

## Dependencies & Execution Order
Setup → Data (T004–T006, after 002 identity tables) → US6 catalog → **US1 engine (MVP)** → scopes/read-write → US2 assignments → US3 admin authority (needed by 002's bootstrap/transfer) → audit/confirmation → privacy composition → Polish. T028 replaces 002's audit double; T015 replaces 001's stub.

## Traceability (FR → tasks)
FR-001..005 T011–T016 · FR-006..008 T020–T023 · FR-009..012 T021, T024, T025 · FR-013..015 T017–T019 · FR-016..018 T018 · FR-019/020 T022, T023 · FR-021..023 T007–T010 · FR-024..030 T009, T029 (domain permissions are declared per domain) · FR-031..033 T031, T032 · FR-034..037 T026, T028, T029.
Total: **36 tasks**. MVP = Setup + Data + US6 + US1.
