---
description: "Task list — Extensibility: plugins, discovery, feature lifecycle (spec 023)"
---

# Tasks: Extensibility — Plugins, Discovery, Feature Lifecycle

**Input**: `specs/023-extensibility/` · **Branch**: `023-extensibility` · **Roadmap**: Phase 8 step 27 · **Tests**: included.
Abbrev: **`PL/`** = `backend/src/portalab/modules/plugins`, **`SDK/`** = `backend/src/portalab/sdk`, **`CAP/`** = `backend/src/portalab/capabilities/plugins`, **`FP/`** = `frontend/src/features/plugins`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` module boundaries, capability registry, jobs · `D-003` permissions/`ConfirmationService`/`AuditSink` · `D-007` event type registry + quarantine · `D-020` settings/toggles · `D-021` PII registry/erasure participants · `D-025` health · registries receiving contributions: 004 nav, 009 widgets, 008 search, 011 calendar, 017 stats, 019 automation, 018 AI tools, 010 categories, 022 themes, 026 i18n, 024 media types, 012 profile sections, 015 product types, 005 connectors (each must expose `unregister(owner)`; follow-ups recorded in `docs/extensibility.md`). Marketplace activation port `ExtensionActivation` is consumed by 015.

## Phase 1: Setup
- [ ] T001 Create `SDK/__init__.py`, `CAP/__init__.py`, `PL/{manifest,store,scanner,resolver,compat,lifecycle,context,ledger,guard,db,update,purge,discovery,modules,activation,api,models}/__init__.py`, `backend/migrations/plugins/versions/`, `plugins/{available,installed}/.gitkeep`, `examples/plugins/hello/`, `FP/{manager,review,diagnostics,pages}/`, `backend/tests/{unit,integration,contract,security}/plugins/`, `frontend/tests/{unit,e2e}/plugins/`
- [ ] T002 [P] Add deps (`packaging`, `jsonschema`; stdlib `tomllib`), declare settings (`plugins.enabled`, `.directory`, `.errorThreshold`, `.hookTimeoutSeconds`, `.statementTimeoutMs`, `.updateProbationMinutes`, `.requireReview`, `.contributionPriority.<key>`) in `PL/settings.py`; permissions `plugins.read|manage|purge` (Admin; manage/purge sensitive, audited) in `PL/permissions.py`; import-linter contract: `plugins` may import only `portalab.sdk`; `core` has no import path to plugins
- [ ] T003 [P] Register event types `plugin.*` and the umbrella `plugin.state_changed` with 007; retention targets (`error_stats`); notification categories `plugins.quarantined|update` (010)

## Phase 2: Foundational — manifest, SDK, package store, schema
### Tests first
- [ ] T004 [P] Write `backend/tests/unit/plugins/test_manifest.py`: schema validation, semver ranges, reserved/Admin-only permission keys rejected, non-namespaced permission/event rejected, `personal_data` without erasure participant declaration rejected, unknown extension points rejected, size limits
- [ ] T005 [P] Write `backend/tests/security/plugins/test_import_scanner.py`: corpus of forbidden imports/calls (`subprocess`, `ctypes`, `os.system`, `portalab.modules.*` internals, `sqlalchemy` engine creation, raw sockets) rejected; allowed SDK-only plugin passes; documented as defense in depth, not a sandbox
- [ ] T006 [P] Write `backend/tests/integration/plugins/test_schema_store.py`: tables, append-only `versions`/`purges`, checksum verification on extract, tampered package refused, versions kept on disk for rollback
### Implementation
- [ ] T007 Implement `SDK/` public surface (`PluginContext`, registration helper protocols, `PluginDb`, `PageDefinition` block types, typed events/permissions/settings helpers) and `PL/models` + Alembic revision for schema `plugins`
- [ ] T008 Implement `PL/manifest/{schema,validator}.py`, `PL/store/package.py` (extract to `plugins/installed/<key>/<version>`, SHA-256), `PL/scanner/scanner.py`

## Phase 3: US6 — Dependencies, compatibility, versioning (P1) 🎯 MVP
**Independent test**: enabling is blocked by missing/incompatible dependencies with named reasons; ordering and cascades are deterministic.
- [ ] T009 [P] [US6] Write `backend/tests/unit/plugins/test_resolver.py`: graph resolution, cycles rejected, missing/incompatible ranges named, topological load order deterministic, disabling with enabled dependents blocked (`plugin.has_dependents`) or cascade preview, property tests on random graphs
- [ ] T010 [P] [US6] Write `backend/tests/integration/plugins/test_compat.py`: portal version range, required capability ranges checked against the 001 registry, incompatible ⇒ state `incompatible` and refusal to enable/update with reasons; additive minor updates pass
- [ ] T011 [US6] Implement `PL/resolver/resolver.py` and `PL/compat/checker.py`, routers `GET /admin/plugins/discovery` (compat preview only at this stage) and `GET /admin/plugins/{key}`

## Phase 4: US1 — Plugin lifecycle (P1)
- [ ] T012 [P] [US1] Write `backend/tests/integration/plugins/test_lifecycle.py`: install (review/consent record) → enable → disable → archive; transitions emit `plugin.*` and `plugin.state_changed` once; state machine forbids invalid transitions; compatibility enforced on enable; schema + role provisioned/removed correctly; first code load sets `needs_restart`; all transitions audited and permissioned
- [ ] T013 [P] [US1] Write `backend/tests/security/plugins/test_role_isolation.py`: plugin role cannot `SELECT` core tables (`identity.users` etc.) nor other plugin schemas; has `statement_timeout`; migrations run with the plugin role on its own Alembic branch; no FKs to core tables
- [ ] T014 [US1] Implement `PL/lifecycle/service.py` (state machine, schema/role provisioning, plugin migrations, events, audit via `AuditSink`), `PL/db/plugin_db.py` (`SET LOCAL ROLE`), `POST /admin/plugins/install`, `POST …/{key}/approve|enable|disable|archive`, CLI `portalab plugin validate|pack|install|enable|disable`

## Phase 5: US4 — Extension points; contribution tracking (P1)
- [ ] T015 [P] [US4] Write `backend/tests/contract/plugins/test_extension_points.py`: sample plugin contributes to every official point (nav, page, widget, action, search provider, calendar source, statistics pack, automation action/trigger events, AI tool, notification category, theme, i18n catalog, permission, setting, event type, capability, product type, media type, profile section, connector); contributions namespaced and permission-gated; deterministic conflict resolution `(priority, plugin key, id)`; singular-point conflicts flagged in diagnostics
- [ ] T016 [US4] Implement `PL/context/plugin_context.py` and `PL/ledger/ledger.py` (record every registration, owner tag `plugin:<key>`), registry adapters under `PL/context/adapters/*.py` calling each owner registry's `register(owner=...)`

## Phase 6: US2 — Disable removes UI cleanly but never deletes data (P1)
- [ ] T017 [P] [US2] Write `backend/tests/integration/plugins/test_clean_removal.py` (**conformance sweep**): after disable and after quarantine, every registry holds zero contributions for the owner (nav, widgets, pages, actions, search, calendar, stats, automations, AI tools, categories, themes, i18n, permissions, settings, events, capabilities, products, media types, profile sections, connectors); shell/dashboard/search render with no broken slots (frontend e2e `frontend/tests/e2e/plugins/no-broken-slots.spec.ts`); plugin data untouched; re-enable restores contributions
- [ ] T018 [P] [US2] Write `backend/tests/integration/plugins/test_purge.py`: data deletion only through `POST /admin/plugins/{key}/purge` (`plugins.purge`, `ConfirmationService`, audit); optional export first; schema and role dropped; `plugins.purges` recorded; purge refused for enabled plugins; core data unaffected
- [ ] T019 [US2] Implement unregistration orchestration (`PL/ledger/removal.py`, forced quarantine on unregister failure) and `PL/purge/service.py` + router, with frontend `FP/manager/PurgeDialog.tsx`

## Phase 7: US3 — Core functional without plugins; failure isolation (P1)
- [ ] T020 [P] [US3] Write `backend/tests/integration/plugins/test_isolation.py`: raising/timeouts/oversized payloads in routes, event handlers, actions, widget providers are guarded; counters feed quarantine at `plugins.errorThreshold`; Admin notified; other plugins and core routes unaffected; plugin event/job handlers execute in the worker not the web process; rate limits enforced; load failure at startup leaves the portal booting
- [ ] T021 [P] [US3] Write `backend/tests/integration/plugins/test_core_without_plugins.py`: full core smoke suite with `plugins.enabled=false` and with zero plugins installed; import-linter proves `core` has no path to plugins; missing/disabled plugin never breaks startup
- [ ] T022 [US3] Implement `PL/guard/guard.py` (`PluginGuard`: timeouts, exception capture, counters in `plugins.error_stats`, rate limits, quarantine), plugin route mounting under `/api/v1/plugins/{key}/…` with manifest permissions, and Observability registration per plugin (`plugin:<key>` component, error fingerprints with plugin key)

## Phase 8: US5 — Events, permissions, capabilities (P1)
- [ ] T023 [P] [US5] Write `backend/tests/integration/plugins/test_events_permissions_caps.py`: plugin event types namespaced and schema-validated by 007 (malformed quarantined); consumers idempotent on duplicate delivery; declared permissions integrate with 003 (namespaced, never reserved), approved at install; capability provide/consume via the 001 registry only; plugin AI tools default non-sensitive and the Admin can only raise sensitivity; plugin personal-data requires an `erasure_participant` (load refused otherwise); no secrets or other users' private data exposed by permission alone
- [ ] T024 [US5] Wire `ctx.events`, `ctx.permissions`, `ctx.capabilities`, `ctx.settings` (scope `plugin` via 020), `ctx.ai`, `ctx.automation` adapters with the above guards and the install-time review record (`plugins.reviews`)

## Phase 9: Updates, rollback, versioning (P1 — FR-021/022/028)
- [ ] T025 [P] [US6] Write `backend/tests/integration/plugins/test_update_rollback.py`: stage new version → compat check → expand-only migration → `pending_restart` → restart → probation; failing health check or failed migration ⇒ automatic rollback to the previous package with data intact and `plugin.update_failed`/`rolled_back` events; destructive migration steps refused until the configured delay; historical plugin data never reinterpreted
- [ ] T026 [US6] Implement `PL/update/service.py` (`update_runs`, probation job, rollback), routers `POST /admin/plugins/{key}/update`, `…/update/confirm-restart`, `…/rollback`, CLI `portalab plugin update`, and the restart-pending banner contract for the shell

## Phase 10: US7 — Admin plugins vs Marketplace plugins; discovery; feature lifecycle (P2)
- [ ] T027 [P] [US7] Write `backend/tests/integration/plugins/test_marketplace_activation.py`: Admin-installed vs Marketplace-linked plugins share one lifecycle; `ExtensionActivation.activate_for_user` grants `plugin:<key>.use` via 003 (per-user plugins) and returns `active|needs_configuration|failed|incompatible`; activation immediate unless configuration required; failure isolated; deactivation/revocation removes the grant
- [ ] T028 [P] [US7] Write `backend/tests/integration/plugins/test_discovery_modules.py`: discovery lists `plugins/available/` packages and Marketplace plugin products with compat preview, never downloads automatically; maturity (`experimental|beta|stable|deprecated`) shown with deprecation notices; first-party module disable (020 toggle + `ModuleRegistry`) removes its contributions via the same ledger path and respects dependents
- [ ] T029 [US7] Implement `PL/activation/service.py` (`ExtensionActivation`), `PL/discovery/service.py`, `PL/modules/registry.py` + routers `GET/PUT /admin/modules`, `POST /admin/modules/{key}/enable|disable`

## Phase 11: US8 — UI extensions bounded by permissions, privacy, design system (P2)
- [ ] T030 [P] [US8] Write `frontend/tests/unit/plugins/page-renderer.test.tsx`: `PageDefinition` blocks (markdown via 011 sanitizer, stat/list/table/chart bound to plugin data endpoints with `FunctionalState`, forms from JSON Schema → plugin actions) render with design-system components only; blocks hidden when the viewer lacks the manifest permission; no plugin JavaScript executed; themes/accessibility prefs apply; assets served image-only with strict CSP
- [ ] T031 [P] [US8] Write `backend/tests/security/plugins/test_ui_bounds.py`: plugin routes default-deny and permission-checked; page data endpoints never return other users' private data by permission alone; asset route blocks non-image types and traversal; markdown XSS corpus inert; action forms validated server-side and audited when sensitive
- [ ] T032 [US8] Implement `FP/pages/PageRenderer.tsx` + block components, plugin asset route, `PL/api/plugin_routes.py` helpers (permission declaration, rate limit, typed state payloads), registration with the 004 navigation assembler for `PageDefinition` routes

## Phase 12: Admin UI, SDK/CLI, docs, hardening
- [ ] T033 Implement admin UI `FP/manager/{PluginList,InstallWizard,ReviewConsent,PluginDetail,UpdatePanel,Diagnostics,DependencyGraph}.tsx` (cascade preview, maturity badges, restart banner, accessible) and `FP/review/*`; `GET /admin/plugins/{key}/diagnostics` (ledger, conflicts, error stats)
- [ ] T034 [P] Build the sample plugin `examples/plugins/hello/` (declarative + code tier, contributes to many points, has `personal_data=false`) and CLI `portalab plugin pack`; publish SDK docs `docs/plugin-authoring.md` (tiers, trust model, isolation limits, expand/contract rule, testing kit)
- [ ] T035 [P] Add plugin-author contract test kit `backend/tests/contract/plugins/kit.py` (manifest validation, import scan, registration/removal sweep, guard behavior) usable in plugin CI
- [ ] T036 [P] Add `/admin/plugins*`, `/admin/modules*`, `/api/v1/plugins/*` to the permission-matrix test, regenerate OpenAPI client, update deployment docs (plugin volume, PostgreSQL role provisioning needs `CREATEROLE`, restart procedure)
- [ ] T037 Run `specs/023-extensibility/quickstart.md` end-to-end; record deviations, open product confirmations (OQ-110..114 defaults) and the per-registry `unregister(owner)` follow-up status

## Dependencies & Order
Setup → Foundational → US6 resolver/compat (MVP) → US1 lifecycle → US4 contributions → US2 clean removal/purge → US3 isolation → US5 events/permissions → updates/rollback → US7 → US8 → admin UI/docs/hardening. The conformance sweep (US2) must stay green as new registries are added by other specs.
**Parallel examples**: T004/T005/T006 · T009/T010 · T012/T013 · T017/T018 · T020/T021 · T030/T031 · T034/T035/T036.
**MVP**: Phases 1–4 (manifest/SDK/store, resolver and compatibility, lifecycle with schema/role isolation).

## Format validation
37 tasks, all checkbox + ID + path; story labels only on story phases.
