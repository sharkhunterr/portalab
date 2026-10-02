---
description: "Task list — Administration & Configuration (spec 020)"
---

# Tasks: Administration & Configuration

**Input**: `specs/020-administration/` · **Branch**: `020-administration` · **Roadmap**: Phase 1 step 4 · **Tests**: included.
Abbrev: **`ADM/`** = `backend/src/portalab/modules/administration`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` kernel `declare_setting`/secrets · `D-002` `IdentityBootstrap`, principal · `D-003` `require()`, `AuditSink` · `D-021` retention/preserve pattern.

## Phase 1: Setup
- [X] T001 Create `ADM/{config,policies,toggles,importexport,firstrun,overview,api,models}/__init__.py`, `backend/migrations/administration/versions/`, `backend/tests/{unit,integration,security}/admin/`, `frontend/src/features/admin/`
- [X] T002 [P] Declare permissions `configuration.manage`, `modules.manage`, `plugins.manage`, `connectors.manage` (all sensitive) in `ADM/permissions.py`
- [X] T003 [P] Declare settings `admin.firstRunLocked`, `admin.configHistoryRetentionDays`, `admin.overviewPanelTimeoutMs` in `ADM/settings.py`

## Phase 2: Foundational
### Tests first
- [X] T004 [P] Write `backend/tests/integration/admin/test_schema.py`: unique (key, scope, scope_ref); `setting_history` append-only; one `first_run` row
- [X] T005 [P] Write `backend/tests/unit/admin/test_registry.py`: duplicate keys rejected at startup; schema/default validated; sensitive flag recorded
### Implementation
- [X] T006 Implement models + Alembic revision for `config.settings`, `config.policies`, `config.setting_history`, `admin.extension_toggles`, `admin.first_run`
- [X] T007 Implement `ADM/config/registry.py` (collects kernel declarations, validates Pydantic schemas, `SettingUpgrade` registration) and replace the in-memory declaration catalog from 001

## Phase 3: US5 — Resolve effective configuration (P1) 🎯 MVP
- [X] T008 [P] [US5] Write `backend/tests/unit/admin/test_resolution.py` (property-style): order code default ▸ global ▸ module ▸ plugin ▸ user within policy; locked keys ignore user values; bounded keys clamp/refuse; user value retained when policy overrides and effective again when policy removed
- [X] T009 [US5] Implement `ADM/config/service.py` (`get`, `set`, `effective_for_user`) with pure resolution in `ADM/config/resolution.py`, encrypted storage for `sensitive` keys via `core.secrets`, per-request memoization only
- [X] T010 [US5] Implement `ADM/policies/service.py` (`default|lock|bound` policies, history, never deleting user values) and routers `POST /admin/policies`, `DELETE /admin/policies/{id}`
- [X] T011 [P] [US5] Write `backend/tests/integration/admin/test_config_api.py`: set/get across scopes, 422 on invalid, sensitive values write-only (never returned/logged/exported), history + audit entry with redacted values

## Phase 4: US5 — Preview, validate, apply (P1)
- [X] T012 [P] [US5] Write `backend/tests/integration/admin/test_preview.py`: `validate` returns diff/warnings/errors without side effects; `apply` emits `admin.config_changed` once (idempotent on retry)
- [X] T013 [US5] Implement `ADM/config/preview.py` and routers `GET /admin/config`, `POST /admin/config/validate`, `PUT /admin/config`; publish `admin.config_changed` and write `setting_history`

## Phase 5: US5 — Preferences facade and read ports (P1)
- [X] T014 [P] [US5] Write `backend/tests/integration/admin/test_preferences.py`: `/me/preferences` limited to `user_overridable` keys, bounded by policy, returns `locked`; erasure participant removes the user's user-scope values
- [X] T015 [US5] Implement routers `GET|PUT /me/preferences` and the erasure/export participants for user-scope settings in `ADM/config/user_prefs.py`
- [X] T016 [P] [US5] Implement the read-port adapters (`identity.*` settings reader for 002, `UserLocalePreferenceReader` and `I18nPolicyReader` for 026) in `ADM/config/ports.py` with contract tests `backend/tests/contract/test_config_ports.py`

## Phase 6: US6 — Enable/disable toggles (P2)
- [X] T017 [P] [US6] Write `backend/tests/integration/admin/test_toggles.py`: toggle writes state + audit + event; data untouched; compatibility hook invoked before enable; re-enable restores; failing hook blocks enable
- [X] T018 [US6] Implement `ADM/toggles/service.py` (`module|plugin|connector|service|automation`, `compatibility_check` hook point for 023) and router `POST /admin/toggles/{kind}/{ref}`; call `set_plugin_permissions_enabled` from 003 for plugins

## Phase 7: US7 — Import/export of configuration (P2)
- [X] T019 [P] [US7] Write `backend/tests/integration/admin/test_import_export.py`: export excludes sensitive values and carries `format_version`; import = validate → conflict report → apply; conflicts never silently overwrite; audited
- [X] T020 [US7] Implement `ADM/importexport/service.py` and routers `POST /admin/config/export|import`

## Phase 8: US4 — Installation / first-run (P1)
- [X] T021 [P] [US4] Write `backend/tests/integration/admin/test_first_run.py`: wizard validates base settings, creates the sole Admin through `IdentityBootstrap`, runs registered optional steps (`services` step contributed by 005, skippable), then answers 410; reset requires an explicit audited action
- [X] T022 [US4] Implement `ADM/firstrun/service.py` (with `FirstRunStep` registry) and router `POST /admin/first-run`; make the CLI `portalab admin bootstrap` (002) and the wizard share the same service

## Phase 9: US1 — Control Center skeleton (P1)
- [X] T023 [P] [US1] Write `backend/tests/integration/admin/test_overview_degraded.py`: panels load independently; a slow/failing provider returns `unavailable` for that panel only; required actions sorted action → impact → criticality → age; panels filtered by permission
- [X] T024 [US1] Implement `ADM/overview/` (`PanelProvider`/`RequiredActionProvider` registries, per-panel timeout from settings, router `GET /admin/overview`) and register the first real panel (configuration/first-run status)
- [X] T025 [P] [US7] Implement the operator CLI wrappers `portalab backup`, `portalab restore`, `portalab migrate --status` in `backend/src/portalab/app/cli.py` (read-only status endpoint; no UI-triggered restore)

## Phase 9b: US2 / US3 / US8 — Domain surfaces, single-Admin & sensitive handling, health/audit panels
- [X] T026 [P] [US2] Write `backend/tests/contract/admin/test_surfaces.py`: every module registers its admin surface (route, label key, required permission) in `AdminSurfaceRegistry`; the Control Center lists only surfaces the Admin may use; a disabled module's surface disappears
- [X] T027 [US2] Implement `ADM/surfaces/registry.py` (`AdminSurfaceRegistry`, owner-tagged) and `GET /admin/surfaces`; domain admin screens themselves are delivered by their owning specs
- [X] T028 [P] [US3] Write `backend/tests/security/admin/test_single_admin_sensitive.py`: single-Admin indicator on admin surfaces; transfer flow delegates to 002 `AdminTransferService`; every sensitive admin action goes through 003 `ConfirmationService` and is audited; no temporary role-delegation option exists anywhere (CD-001)
- [X] T029 [P] [US8] Write `backend/tests/integration/admin/test_health_audit_panels.py` and implement `ADM/overview/panels/{health,infrastructure,storage,audit}.py` as `PanelProvider`s fed by 025, 006 and 021 (stubs until those land), each panel failing independently

## Phase 10: Polish & validation
- [X] T030 [P] Build admin UI in `frontend/src/features/admin/` (config editor with preview, policies, toggles, first-run wizard, overview) with loading/error/unauthorized states, keyboard, axe tests, externalized strings
- [X] T031 [P] Add observability (`ADM/observability.py`): config changes, invalid stored values, panel latency/failures; test redaction
- [X] T032 [P] Write the stored-value upgrade test scaffold `backend/tests/integration/admin/test_setting_upgrades.py` (old version → new schema, never silent reset)

## Cross-spec obligations (audit 2026-10-01 — see `decisions/PLAN_FOLLOWUPS.md`)
- [X] T033 Validate `dashboard.widgetPolicies` keys against registered widgets, let `ToggleService` delegate dependency checks to 023's `ModuleRegistry`, and accept plugin-scope settings declared from plugin manifests; test `backend/tests/integration/admin/test_dynamic_settings.py` (F18)
- [X] T034 [P] Expose owner-tagged registration on the setting registry and `AdminSurfaceRegistry`: `register(..., owner="module:<id>|plugin:<key>")` and `unregister(owner)`, with a test in `backend/tests/unit/admin/test_registry_owner.py` proving all contributions of an owner disappear (required by 023's conformance sweep, F20)

- [X] T035 Add migration-upgrade test `backend/tests/migrations/test_upgrade_administration.py` (021 → administration) and run the full validation; record results

## Dependencies & Execution Order
Setup → Foundational → **Resolution (MVP)** → Preview/apply → Preferences + ports → Toggles/Import-export (parallel) → First-run → Control Center → Polish. T022 reuses 002's bootstrap service; T018 reuses 003's catalog toggle.

## Traceability (FR → tasks)
Spec 020 FR-001..004 T023–T024 · FR-005/006 T018, T024 (domain panels arrive with their specs) · FR-007 T021–T022 · FR-008/009 T011, T013 · FR-010/011 T021–T022 · FR-012/013 T008–T013 · FR-014/015 T017–T018 · FR-016 T019–T020 · FR-017..020 T018, T025 (backup/update/compatibility by CLI + hook) · FR-021..023 T024 (health/infra/audit panels contributed later) · FR-024..026 T013, T023, T031.
Cross-spec: 002 FR-013/014/015/017 (preferences) T014–T016.
Total: **29 tasks**. MVP = Setup + Foundational + Resolution.
