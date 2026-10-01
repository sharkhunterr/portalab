# Implementation Plan: Administration & Configuration

**Branch**: `020-administration` | **Date**: 2026-10-01 | **Spec**: `specs/020-administration/spec.md`
**Roadmap**: Phase 1 step 4 *Configuration* (the Control Center panels/other admin domains follow as their specs land).

## Summary
Module `administration` owns the **transversal configuration system** (CD-011): persistent store, typed/versioned settings, Global → Module → Plugin → User resolution with admin policies (lock/bound) that retain user preferences, preview/validate/apply, config import/export, the enable/disable toggle service, the first-run wizard (over `IdentityBootstrap`), and the Control Center aggregation API with panel and required-action providers. It does not own the settings' meaning (each module), audit rules, or backup/restore semantics beyond operator CLI.

## Technical Context
**Language**: Python 3.12 · **New deps**: none (Pydantic for schemas) · **Storage**: schemas `config`, `admin` · **Testing**: pytest (real PG), property tests for resolution · **Constraints**: no other config store anywhere; sensitive values encrypted; changes audited; resolution deterministic · **Scale**: hundreds of keys, per-request effective reads cached per request.

## Constitution Check — PASS
XVIII configuration hierarchy · II/XX single config engine · VI sensitive values/permissions · XIII audit · XIX versioned settings & upgrades · IX Control Center panels degrade independently · XII admin UI WCAG 2.2 AA. No violations.

## 1. Architecture
```
declare_setting() (modules/plugins at import) ─▶ SettingRegistry ──▶ ConfigService ◀── API / UI
                                                     │  resolve: code default ▸ Global ▸ Module ▸ Plugin ▸ User, then policies
                                 config.settings · config.policies · config.setting_history
Toggle service ─▶ admin.extension_toggles ─▶ events (navigation/registry consumers)
Control Center: PanelProvider[*] + RequiredActionProvider[*] ─▶ /admin/overview (independent, per-panel state)
First run: wizard ─▶ IdentityBootstrap (002) ─▶ admin.first_run
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `SettingRegistry` | collect declarations, validate schemas, detect duplicate keys | kernel | `declare_setting` | startup fails on conflicts | declaration tests |
| `ConfigService` | get/set/validate/effective, upgrades of stored values | `core.db`, `core.secrets` | `admin.config` capability | pure resolution; sensitive write-only | resolution property tests |
| `PolicyService` | lock/bound/default policies, retention of user values | ConfigService | API | policy never deletes user value | preserve/restore tests |
| `PreviewService` | diff + warnings before apply | ConfigService | `validate()` | no side effects | preview tests |
| `ConfigPorts` adapters | implement read ports for identity (`identity.*` keys) and i18n (`UserLocalePreferenceReader`, `I18nPolicyReader`) | ConfigService | ports from 002/026 | thin | contract tests |
| `ToggleService` | enable/disable module/plugin/connector/service/automation, data retained | `core.db`, events | API + events | audited; compatibility check hook (023) | toggle tests |
| `ImportExportService` | versioned JSON export (no secrets), validate/conflict/apply import | ConfigService | API | conflicts surfaced, never silent overwrite | import/export tests |
| `FirstRunService` | guarded wizard flow | `IdentityBootstrap` | API | once only; reset audited | first-run tests |
| `ControlCenter` | `/admin/overview` aggregation + required actions | providers | API | panels independent, failures isolated | degraded-panel tests |
| `OperatorCLI` | `portalab backup|restore|migrate` wrappers, status endpoints read-only | kernel CLI | CLI | no UI restore (OQ-96) | CLI smoke |

## 3. Data Model / 4. Contracts
`data-model.md`, `contracts/config-contracts.md`.

## 5. Events
Produced: `admin.config_changed`, `admin.policy_changed`, `admin.*_toggled`, `admin.firstrun_completed`, `admin.import_performed|export_performed` via `EventPublisher` (dedup `(key, scope, scope_ref, change_seq)`). Consumed: none initially (navigation/registry consume toggles later). Failure: outbox retry; consumers idempotent.

## 6. Permissions & Security
All routes via `require()`. `configuration.manage`, `modules.manage`, `plugins.manage`, `connectors.manage` flagged sensitive; every change audited with redacted old/new values. Sensitive settings are write-only and never in exports/logs. User-tier endpoints limited to the caller and to `user_overridable` keys within policy bounds.

## 7. Configuration
Self-referential keys declared here: `admin.firstRunLocked`, `admin.configHistoryRetentionDays`, `admin.overviewPanelTimeoutMs`. Existing declarations from 002/003/021 become persisted/serveable.

## 8. External Integrations
None.

## 9. Error Handling & Resilience
Invalid value ⇒ 422 with field errors, nothing applied · unknown key ⇒ 404 · stored value failing a new schema ⇒ upgrade function or fall back to code default + `admin.config_invalid` observability signal (never crash) · panel provider timeout/failure ⇒ that panel returns `unavailable`, others render · config store unreachable ⇒ code defaults served read-only, writes refused.

## 10. Observability
Counters: config changes, policy overrides, invalid stored values, panel latency/failures, toggle changes; structured logs with redaction.

## 11. Testing Strategy
Unit/property: resolution order, policy lock/bound with preference retained, schema upgrades. Integration: set/get across scopes, preview vs apply, sensitive write-only, history/audit entries, import conflicts, first-run once-only, panel isolation. Contract: adapters for 002/026 ports. Security: permission matrix, secret absence in exports/logs, user cannot change non-overridable keys. Migration: upgrade from 021.

## 12. Migration / Versioning
`config`/`admin` Alembic revisions; setting `schema_version` + registered upgrades; export format versioned (`format_version`); API `/api/v1`.

## 13. Cross-Spec Dependencies
Prerequisites: 001 kernel (`declare_setting`, secrets), 002 (`IdentityBootstrap`, principal), 003 (`require`, `AuditSink`), 021 (preference-retention pattern). Exposes: `admin.config`, panel/required-action registries, toggle service, preference reader adapters (used by 026 i18n, 010, 022, 009). Later: every module declares/reads settings; 004 consumes toggles; 007 adopts events.

## 14. Implementation Phases
1 Data & registry → 2 ConfigService & resolution → 3 Policies & preview → 4 Sensitive values, history, audit → 5 Preference facade (`/me/preferences`) + read-port adapters → 6 Toggles → 7 Import/export → 8 First-run → 9 Control Center skeleton + CLI → 10 UI & tests.

## 15. Technical Decisions & Trade-offs
`research.md` R1–R11. Single typed store with code-declared schemas trades flexibility for consistency and safe upgrades.

## 16. Risks / Open Technical Questions
- **R1** Hierarchy semantics for `Module` vs `Plugin` scope (which wins when both set) — plan default: plugin ▸ module ▸ global, user last within policy; confirm with 023's plan.
- **R2** Backup/restore scope undecided (OQ-96) ⇒ CLI only.
- **R3** Admin UI breadth grows as modules land (panels contributed incrementally).
- **R4** Stored-value upgrade functions must be tested per release.

## Project Structure
```text
backend/src/portalab/modules/administration/{config,policies,toggles,importexport,firstrun,overview,api,models}/
backend/migrations/administration/versions/ · frontend/src/features/admin/
```
