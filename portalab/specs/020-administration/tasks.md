---
description: "Task list — Administration & Configuration (spec 020)"
---

# Tasks: Administration & Configuration

**Input**: `specs/020-administration/` · **Branch**: `020-administration` · **Roadmap**: Phase 1 step 4 · **Tests**: included.
Abbrev: **`ADM/`** = `backend/src/portalab/modules/administration`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` kernel `declare_setting`/secrets · `D-002` `IdentityBootstrap`, principal · `D-003` `require()`, `AuditSink` · `D-021` retention/preserve pattern.

## Phase 1: Setup
- [ ] T001 Create `ADM/{config,policies,toggles,importexport,firstrun,overview,api,models}/__init__.py`, `backend/migrations/administration/versions/`, `backend/tests/{unit,integration,security}/admin/`, `frontend/src/features/admin/`
- [ ] T002 [P] Declare permissions `configuration.manage`, `modules.manage`, `plugins.manage`, `connectors.manage` (all sensitive) in `ADM/permissions.py`
- [ ] T003 [P] Declare settings `admin.firstRunLocked`, `admin.configHistoryRetentionDays`, `admin.overviewPanelTimeoutMs` in `ADM/settings.py`

## Phase 2: Foundational
### Tests first
- [ ] T004 [P] Write `backend/tests/integration/admin/test_schema.py`: unique (key, scope, scope_ref); `setting_history` append-only; one `first_run` row
- [ ] T005 [P] Write `backend/tests/unit/admin/test_registry.py`: duplicate keys rejected at startup; schema/default validated; sensitive flag recorded
### Implementation
- [ ] T006 Implement models + Alembic revision for `config.settings`, `config.policies`, `config.setting_history`, `admin.extension_toggles`, `admin.first_run`
- [ ] T007 Implement `ADM/config/registry.py` (collects kernel declarations, validates Pydantic schemas, `SettingUpgrade` registration) and replace the in-memory declaration catalog from 001

## Phase 3: US — Resolve effective configuration (P1) 🎯 MVP
- [ ] T008 [P] Write `backend/tests/unit/admin/test_resolution.py` (property-style): order code default ▸ global ▸ module ▸ plugin ▸ user within policy; locked keys ignore user values; bounded keys clamp/refuse; user value retained when policy overrides and effective again when policy removed
- [ ] T009 Implement `ADM/config/service.py` (`get`, `set`, `effective_for_user`) with pure resolution in `ADM/config/resolution.py`, encrypted storage for `sensitive` keys via `core.secrets`, per-request memoization only
- [ ] T010 Implement `ADM/policies/service.py` (`default|lock|bound` policies, history, never deleting user values) and routers `POST /admin/policies`, `DELETE /admin/policies/{id}`
- [ ] T011 [P] Write `backend/tests/integration/admin/test_config_api.py`: set/get across scopes, 422 on invalid, sensitive values write-only (never returned/logged/exported), history + audit entry with redacted values

## Phase 4: US — Preview, validate, apply (P1)
- [ ] T012 [P] Write `backend/tests/integration/admin/test_preview.py`: `validate` returns diff/warnings/errors without side effects; `apply` emits `admin.config_changed` once (idempotent on retry)
- [ ] T013 Implement `ADM/config/preview.py` and routers `GET /admin/config`, `POST /admin/config/validate`, `PUT /admin/config`; publish `admin.config_changed` and write `setting_history`

## Phase 5: US — Preferences facade and read ports (P1)
- [ ] T014 [P] Write `backend/tests/integration/admin/test_preferences.py`: `/me/preferences` limited to `user_overridable` keys, bounded by policy, returns `locked`; erasure participant removes the user's user-scope values
- [ ] T015 Implement routers `GET|PUT /me/preferences` and the erasure/export participants for user-scope settings in `ADM/config/user_prefs.py`
- [ ] T016 [P] Implement the read-port adapters (`identity.*` settings reader for 002, `UserLocalePreferenceReader` and `I18nPolicyReader` for 026) in `ADM/config/ports.py` with contract tests `backend/tests/contract/test_config_ports.py`

## Phase 6: US — Enable/disable toggles (P2)
- [ ] T017 [P] Write `backend/tests/integration/admin/test_toggles.py`: toggle writes state + audit + event; data untouched; compatibility hook invoked before enable; re-enable restores; failing hook blocks enable
- [ ] T018 Implement `ADM/toggles/service.py` (`module|plugin|connector|service|automation`, `compatibility_check` hook point for 023) and router `POST /admin/toggles/{kind}/{ref}`; call `set_plugin_permissions_enabled` from 003 for plugins

## Phase 7: US — Import/export of configuration (P2)
- [ ] T019 [P] Write `backend/tests/integration/admin/test_import_export.py`: export excludes sensitive values and carries `format_version`; import = validate → conflict report → apply; conflicts never silently overwrite; audited
- [ ] T020 Implement `ADM/importexport/service.py` and routers `POST /admin/config/export|import`

## Phase 8: US — Installation / first-run (P1)
- [ ] T021 [P] Write `backend/tests/integration/admin/test_first_run.py`: wizard validates base settings, creates the sole Admin through `IdentityBootstrap`, then answers 410; reset requires an explicit audited action
- [ ] T022 Implement `ADM/firstrun/service.py` and router `POST /admin/first-run`; make the CLI `portalab admin bootstrap` (002) and the wizard share the same service

## Phase 9: US — Control Center skeleton (P1)
- [ ] T023 [P] Write `backend/tests/integration/admin/test_overview_degraded.py`: panels load independently; a slow/failing provider returns `unavailable` for that panel only; required actions sorted action → impact → criticality → age; panels filtered by permission
- [ ] T024 Implement `ADM/overview/` (`PanelProvider`/`RequiredActionProvider` registries, per-panel timeout from settings, router `GET /admin/overview`) and register the first real panel (configuration/first-run status)
- [ ] T025 [P] Implement the operator CLI wrappers `portalab backup`, `portalab restore`, `portalab migrate --status` in `backend/src/portalab/app/cli.py` (read-only status endpoint; no UI-triggered restore)

## Phase 10: Polish & validation
- [ ] T026 [P] Build admin UI in `frontend/src/features/admin/` (config editor with preview, policies, toggles, first-run wizard, overview) with loading/error/unauthorized states, keyboard, axe tests, externalized strings
- [ ] T027 [P] Add observability (`ADM/observability.py`): config changes, invalid stored values, panel latency/failures; test redaction
- [ ] T028 [P] Write the stored-value upgrade test scaffold `backend/tests/integration/admin/test_setting_upgrades.py` (old version → new schema, never silent reset)
- [ ] T029 Add migration-upgrade test (021 → administration) and run the full validation; record results

## Dependencies & Execution Order
Setup → Foundational → **Resolution (MVP)** → Preview/apply → Preferences + ports → Toggles/Import-export (parallel) → First-run → Control Center → Polish. T022 reuses 002's bootstrap service; T018 reuses 003's catalog toggle.

## Traceability (FR → tasks)
Spec 020 FR-001..004 T023–T024 · FR-005/006 T018, T024 (domain panels arrive with their specs) · FR-007 T021–T022 · FR-008/009 T011, T013 · FR-010/011 T021–T022 · FR-012/013 T008–T013 · FR-014/015 T017–T018 · FR-016 T019–T020 · FR-017..020 T018, T025 (backup/update/compatibility by CLI + hook) · FR-021..023 T024 (health/infra/audit panels contributed later) · FR-024..026 T013, T023, T027.
Cross-spec: 002 FR-013/014/015/017 (preferences) T014–T016.
Total: **29 tasks**. MVP = Setup + Foundational + Resolution.
