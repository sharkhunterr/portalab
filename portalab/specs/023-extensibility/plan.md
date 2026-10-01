# Implementation Plan: Extensibility — Plugins, Discovery, Feature Lifecycle

**Branch**: `023-extensibility` | **Date**: 2026-10-01 | **Spec**: `specs/023-extensibility/spec.md`
**Roadmap**: Phase 8 step 27 *Plugins / Discovery / Feature Lifecycle* (last step). Resolves the packaging/isolation decision deferred by spec 001, and unifies the extension registries already exposed by 003, 004, 005, 007, 008, 009, 010, 011, 012, 015, 017, 018, 019, 020, 022, 024, 026.

## Summary
Module `plugins` owns the **extension registry and lifecycle** (installed → enabled ⇄ disabled → archived, update with rollback, quarantine), a **tiered plugin model** (declarative manifests with no code; trusted in-process Python plugins installed only by the Admin; sandboxed out-of-process plugins reserved for the future), the public **`portalab.sdk`** with a tracked `PluginContext` (so every contribution can be removed cleanly), dependency/compatibility resolution, per-plugin data isolation (own schema + PostgreSQL role), failure isolation via `PluginGuard`, namespaced permissions and events, discovery of installable packages, maturity/deprecation tracking, and first-party **module** enable/disable on the same machinery. The core never imports plugins and remains fully functional without them.

## Technical Context
**Language**: Python 3.12 + TypeScript/React 19 · **Deps (new)**: `packaging` (semver/ranges), `tomli`/stdlib `tomllib` (manifest), `jsonschema` · **Storage**: schema `plugins` + per-plugin schemas/roles · **Testing**: pytest real PG (role isolation, migrations), conformance sweep across registries, fault-injection for guard/quarantine, sample plugin; Vitest; Playwright · **Constraints**: no data deletion on disable, clean contribution removal, no plugin JS executed in the SPA (v1), plugin can't touch core tables, honest isolation limits · **Scale**: tens of plugins.

## Constitution Check — PASS
III Extensibility First (core of the principle) · I/VI default-deny, review/consent, namespaced permissions, no bypass · VII plugin data under 021 (mandatory erasure participant) · IX isolation, quarantine, graceful degradation · XIX versioning, expand/contract, rollback · XX plugins reuse existing registries/capabilities, no parallel mechanisms · XIII audited lifecycle actions. No violations (isolation limits documented, not claimed away).

## 1. Architecture
```
Admin ─ discover(plugins/available · Marketplace plugin products) ─▶ Validator(manifest schema, checksum, import scan, compat, deps) ─▶ Review/consent ─▶ install to plugins/installed/<key>/<ver>
enable ─▶ DependencyResolver ─▶ create schema+role ─▶ expand migrations (plugin role) ─▶ load entry point (code plugins; first load ⇒ needs_restart) ─▶ register(ctx)
PluginContext ─▶ registries (nav·pages·widgets·actions·search·calendar·stats·automation·ai·notify·themes·i18n·permissions·settings·events·capabilities·products·media·profile·connectors)
      every registration ─▶ ContributionLedger(plugin, point, id, priority)          disable/quarantine ─▶ unregister_all(owner=plugin:<key>)
Runtime hooks ─▶ PluginGuard(timeout · try/except · counters · rate limits) ─▶ Observability(025) ─▶ quarantine at threshold
Update: stage ─▶ compat ─▶ expand migrations ─▶ pending_restart ─▶ restart ─▶ probation(health) ─▶ success | rollback to previous
Purge (separate, confirmed, audited): optional export ─▶ drop schema/role ; Modules: ModuleRegistry + 020 toggles + same ledger removal
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `Manifest` + validator | schema, semver ranges, permission/event/setting checks | jsonschema | `validate()` | rejects reserved permissions, invalid ranges | schema tests |
| `PackageStore` | extract/verify checksum, versions on disk, rollback copies | filesystem | internal | integrity check; no core-env install | store tests |
| `ImportScanner` | static AST scan for forbidden imports/calls (defense in depth) | ast | internal | allow only `portalab.sdk` + stdlib allow-list | scanner tests |
| `DependencyResolver` | graph, cycles, missing, ranges, order, cascade preview | manifests, registry | internal/API | deterministic | graph property tests |
| `CompatibilityChecker` | portal version + capability ranges | 001 registry | internal | blocks enable/update | compat tests |
| `PluginLifecycle` | state machine, schema/role provisioning, migrations, events | `core.db` | API/CLI | transitions audited; data retained | lifecycle tests |
| `PluginContext` + `ContributionLedger` | tracked registrations, removal | all registries | SDK | every registry supports `unregister(owner)` | **conformance sweep** |
| `PluginGuard` | timeouts, exception capture, counters, rate limits, quarantine | 025 | wrapper | never raises into core | fault-injection tests |
| `PluginDb` | role-bound sessions, statement timeouts | PostgreSQL roles | SDK | no core table access | role-isolation tests |
| `UpdateService` | stage/migrate/restart/probation/rollback | lifecycle | API | expand-only migrations; auto-rollback | update tests |
| `PurgeService` | export + drop schema/role | exports, audit | API | permissioned, confirmed | purge tests |
| `DiscoveryService` | scan available packages, Marketplace products, compat preview | 015, filesystem | API | offline; no auto-download | discovery tests |
| `ModuleRegistry` | first-party module enable/disable + dependents | 020 toggles | API | same removal path | module tests |
| `ExtensionActivation` | per-user activation for Marketplace plugins | 003, 015 | port | grants `plugin:<key>.use` only | activation tests |
| Page renderer + admin UI | declarative pages, admin manager | 022/004 | components | design-system only; accessible | a11y/e2e |

## 3. Data Model — `data-model.md` · 4. Contracts — `contracts/extensibility-contracts.md`

## 5. Events
Produced: `plugin.installed|enabled|disabled|updated|update_failed|rolled_back|quarantined|archived|purged|configuration_changed` plus the umbrella `plugin.state_changed` (consumed by the registries of 004/009/008/015/018/019/017/026). Plugin events `plugin.<key>.<type>` validated/quarantined by 007; plugin consumers idempotent via `ctx.idempotent_effect`; plugin event/job handlers execute in the worker. Dedup `(plugin_key, seq)`.

## 6. Permissions & Security
`plugins.read|manage` (Admin; manage sensitive, audited), `plugins.purge` (separate, confirmation), `modules.manage` (020). Review/consent record on install; plugin permissions namespaced `plugin:<key>.*`, never reserved; per-user plugins gated by `plugin:<key>.use`. Data isolation by schema + role; capabilities are the only door to core data; secrets never exposed to plugins except their own declared settings (`core.secrets` scoped per plugin); plugin routes default-deny with manifest-declared permissions and rate limits; assets image-only under strict CSP; import scan + checksum as defense in depth (documented as **not** a sandbox); AI tools from plugins default non-sensitive classes and may only be raised by the Admin; plugin personal data requires an `erasure_participant`.

## 7. Configuration — `data-model.md` settings (declared into 020).

## 8. External Integrations — none (offline discovery; remote index is a future opt-in).

## 9. Error Handling & Resilience
Hook exception/timeout ⇒ guarded, counted, request/handler fails alone · threshold ⇒ quarantine (contributions removed, data intact, notification to Admin) · load failure at startup ⇒ plugin `incompatible`/`failed`, portal starts normally (core has no import path to plugins) · migration failure ⇒ transaction rollback, plugin stays on prior version (`update_failed`) · restart pending ⇒ explicit state and banner · dependency removed ⇒ dependents blocked with named reason · registry unregister failure ⇒ logged, plugin forced to quarantined and ledger flagged for diagnostics.

## 10. Observability
Per-plugin health (error rate, last success, hook latency, quarantines), contribution counts, update outcomes; registers each plugin as component `plugin:<key>` and `plugins` overall with 025 (technical + functional axes); error fingerprints include the plugin key.

## 11. Testing Strategy
Unit: manifest/semver/range validation, dependency graph (cycles/missing/cascade), import scanner corpus, conflict ordering. Integration (real PG): lifecycle incl. schema/role provisioning, plugin role denied on core tables, expand migrations, update/probation/rollback with fault injection, purge with export. **Conformance sweep**: a sample plugin contributing to every extension point is enabled then disabled/quarantined — every registry must hold zero entries for the owner and the shell/dashboard/search must render without broken slots. Isolation: raising/timeouts/rate limits, quarantine, worker-only handlers. Core-without-plugins: full core test-suite run with `plugins.enabled=false` and with no plugins installed. Security: reserved permission attempts, event schema abuse, asset serving, SSRF-ish inputs, personal-data flag without participant refused. Frontend: page renderer blocks, install review/consent, cascade preview, accessibility.

## 12. Migration / Versioning
Alembic revision for `plugins`; per-plugin Alembic branches (`plugin_<key>`) run with the plugin role; manifest `schema_version` with upgraders; SDK semver (`portalab.sdk` major bumps announced with deprecation period); expand/contract policy documented and enforced by the update checker.

## 13. Cross-Spec Dependencies
Prerequisites: 001 (module boundaries, capability registry, jobs), 003 (permissions/audit/`ConfirmationService`), 007 (event type registry, quarantine), 020 (settings, toggles), 021 (PII registry/erasure participants), 025 (health), 004/009/008/011/012/015/017/018/019/022/024/026/010/005 (registries receiving contributions). Provides: `ExtensionActivation` to 015, `plugin.state_changed` to all registries. **Follow-ups in earlier plans**: each registry must expose `unregister(owner)` (small addition across their implementations; verified by the conformance sweep) and a plugin-aware ownership tag on contributions.

## 14. Implementation Phases
1 Manifest/SDK skeleton + validator + package store → 2 Dependency/compat resolver → 3 Lifecycle + schema/role provisioning + migrations + events → 4 PluginContext + ledger + registry adapters (nav, widgets, pages) + guard/quarantine → 5 Remaining registry adapters + conformance sweep → 6 Permissions/events/capabilities/settings integration + AI/automation guards → 7 Update/rollback + purge → 8 Discovery + module registry/feature lifecycle → 9 Marketplace activation + admin UI + page renderer → 10 Sample plugin, CLI, docs, hardening.

## 15. Technical Decisions — `research.md` R1–R16.

## 16. Risks / Open Technical Questions
- **R1** OQ-110..114 use plan defaults (research); **product confirmation requested** (trust model = Admin-only, tier scope, restart-on-update, no plugin-defined extension points, data ownership/purge).
- **R2** **In-process Python plugins are trusted code**: no preemption or memory caps, so a malicious or buggy plugin can still harm the process; guard + role isolation limit blast radius but Tier 3 is the answer for untrusted code (clearly documented, not hidden).
- **R3** Python module unloading is unreliable: updates and first loads require a graceful restart (explicit state/UX).
- **R4** Every registry must implement owner-based unregister: tracked as follow-ups per earlier plan and enforced by the conformance sweep.
- **R5** Declarative-only UI limits plugin richness in v1 (deliberate; sandboxed UI is a future tier).
- **R6** Per-user plugin activation via permissions assumes 003 supports plugin-scoped grants issued by Marketplace (follow-up with 015).
- **R7** Role-per-plugin provisioning requires a PostgreSQL role with `CREATEROLE` for the platform migrator (operational note in deployment docs).

## Project Structure
```text
backend/src/portalab/{sdk, capabilities/plugins, modules/plugins/{manifest,store,scanner,resolver,compat,lifecycle,context,ledger,guard,db,update,purge,discovery,modules,activation,api,models}} · backend/migrations/plugins/versions/ · plugins/{available,installed}/ · examples/plugins/hello/
frontend/src/features/plugins/{manager,review,diagnostics,pages}
```
