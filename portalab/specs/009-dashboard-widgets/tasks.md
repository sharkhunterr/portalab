---
description: "Task list — Dashboard & Widget System (spec 009)"
---

# Tasks: Dashboard & Widget System

**Input**: `specs/009-dashboard-widgets/` · **Branch**: `009-dashboard-widgets` · **Roadmap**: Phase 4 step 12 · **Tests**: included.
Abbrev: **`DB/`** = `backend/src/portalab/modules/dashboard`, **`CAP/`** = `backend/src/portalab/capabilities/dashboard`, **`FD/`** = `frontend/src/features/dashboard`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` kernel · `D-002` principal + `OnboardingTracker` · `D-003` `authorize` · `D-004` shell/SSE stream · `D-020` settings/policies · `D-022` `FunctionalState`, `PolicyField`, density · `D-026` formatting · `D-007` events · `D-025` health. Domain widgets/providers are delivered by their owning specs through the SDK; this plan ships the framework plus first-party sample widgets (services health from 006, announcements placeholder).

## Phase 1: Setup
- [ ] T001 Create `CAP/__init__.py`, `DB/{registry,overlay,conditions,service,gateway,starter,summary,invalidate,api,models}/__init__.py`, `backend/migrations/dashboard/versions/`, `FD/{grid,frame,templates,catalog,summary,edit}/`, `backend/tests/{unit,integration,contract,security}/dashboard/`, `frontend/tests/{unit,e2e}/dashboard/`
- [ ] T002 [P] Declare settings (`dashboard.widgetPolicies`, `dashboard.starterLayout`, `dashboard.sinceLastLogin.{lookbackDays,maxItems,inactivityGapMinutes,types}`, `dashboard.widgetTimeoutMs`) in `DB/settings.py` with schema validation against registered widget keys; permission `dashboard.manage` (audited) in `DB/permissions.py`
- [ ] T003 [P] Register `widget_instances` as `preference` personal data in the PII registry and register 020/021 export+erasure participant for `dashboard.*` in `DB/privacy.py`

## Phase 2: Foundational — contracts, schema, registry
### Tests first
- [ ] T004 [P] Write `backend/tests/unit/dashboard/test_registry.py`: valid definition registers; invalid schema/duplicate key rejected; unregister keeps stored instances; plugin-sourced keys namespaced
- [ ] T005 [P] Write `backend/tests/integration/dashboard/test_schema.py`: tables, FK only to `identity.users(id)`, unique constraints, `layout_version` increments
### Implementation
- [ ] T006 Implement `CAP/` contracts (`WidgetDefinition`, `WidgetDataProvider`, `WidgetPayload`, `ChangeSummaryProvider`, condition types)
- [ ] T007 Implement `DB/models` + Alembic revision for `dashboard.user_dashboards`, `dashboard.widget_instances`
- [ ] T008 Implement `DB/registry/registry.py` (`register_widget`, `unregister_widget`, catalog query) per T004

## Phase 3: US1 — Independently-loading dashboard resilient to outages (P1) 🎯 MVP
**Independent test**: one backing service down ⇒ only its widget shows a failure state; others load.
- [ ] T009 [P] [US1] Write `backend/tests/integration/dashboard/test_widget_gateway.py`: provider timeout ⇒ `unavailable` payload (HTTP 200); provider exception ⇒ `error`; partial data ⇒ `partial` with reasons; stale computed from `as_of`/`stale_after_s`; permission denied ⇒ `unauthorized` state without data; one slow provider does not delay another request
- [ ] T010 [P] [US1] Write `frontend/tests/unit/dashboard/widget-frame.test.tsx`: crashing widget renders `error` state in its own frame; siblings unaffected; each frame fetches independently; loading/available/partial/stale/unavailable/no-data render through `FunctionalState`
- [ ] T011 [US1] Implement `DB/gateway/router.py` (`GET /widgets/{key}/data`) with per-widget timeout, state mapping, and authorization through provider
- [ ] T012 [US1] Implement `FD/frame/WidgetFrame.tsx` (ErrorBoundary + Suspense + query) and `FD/DashboardPage.tsx` rendering the effective dashboard
- [ ] T013 [US1] Implement first-party sample widgets: services health summary (006 `health.service_state` provider, `DB/widgets/services.py` + `FD/widgets/ServicesHealth.tsx`) and a static "welcome/next steps" widget

## Phase 4: US8 — Presentation independent from functional state (P1)
- [ ] T014 [P] [US8] Write `frontend/tests/a11y/widget-states.spec.tsx`: every widget state under three themes and high contrast keeps meaning, non-color cue and visibility of critical info; no widget defines its own state styling (lint)
- [ ] T015 [US8] Add lint rule/test forbidding state colors outside `FunctionalState` in `FD/` and wire the 022 theme matrix into the dashboard gallery story

## Phase 5: US2 — Personalize the dashboard within policy (P1)
- [ ] T016 [P] [US2] Write `backend/tests/integration/dashboard/test_instances_crud.py`: add/hide/remove/reorder/resize/configure persisted; hide retains config and re-add restores it; remove discards it; `If-Match` conflict ⇒ 409; invalid config ⇒ 422; unavailable/unpermitted widget cannot be added; multiple-instance rule
- [ ] T017 [P] [US2] Write `frontend/tests/e2e/dashboard/personalize.spec.ts`: keyboard-only add/move/resize/hide (no drag-only path), persistence across a second browser context, touch targets
- [ ] T018 [US2] Implement `DB/service/service.py` (CRUD, batch `PUT /dashboard/layout`, config validation + upgraders, optimistic concurrency) and routers `GET /dashboard`, `GET /dashboard/catalog`, `POST|PATCH|DELETE /dashboard/widgets`
- [ ] T019 [US2] Implement frontend edit mode `FD/edit/EditMode.tsx`, `FD/catalog/CatalogDrawer.tsx`, keyboard move/resize controls, widget config forms from JSON Schema, optional drag enhancement behind the same handlers
- [ ] T020 [US2] Emit `dashboard.layout_changed` (counts only, dedup `(user_id, layout_version)`) via `EventPublisher` in `DB/service/events.py`

## Phase 6: US3 — Admin widget policies (P1)
- [ ] T021 [P] [US3] Write `backend/tests/unit/dashboard/test_overlay.py`: property tests for free/default/mandatory/locked/conditional/disabled; mandatory cannot be hidden/removed; locked cannot move/resize/reconfigure; disabled absent; conditional only when true; **policy tightening then relaxing restores the user's prior stored state**; stored rows never mutated by overlay
- [ ] T022 [P] [US3] Write `backend/tests/unit/dashboard/test_conditions.py`: catalog (`role_in`, `permission`, `service_state`, `campaign_active` stub, `module_enabled`, `data_present`); unknown condition ⇒ hidden + diagnostic; no free-form expressions
- [ ] T023 [US3] Implement `DB/overlay/overlay.py` (`PolicyOverlay.effective`) and `DB/conditions/evaluator.py`; apply server-side enforcement on every write in T018 (`dashboard.policy_locked`)
- [ ] T024 [US3] Implement `GET/PUT /admin/dashboard/policies` and `/admin/dashboard/starter` (`dashboard.manage`, validated against registry, audited through 020/`AuditSink`) and frontend `PolicyField` badges (locked/mandatory) in `FD/`

## Phase 7: US4 — Automatic starter dashboard at onboarding (P1)
- [ ] T025 [P] [US4] Write `backend/tests/integration/dashboard/test_starter.py`: onboarding `dashboard` step applies starter within permissions/policy; idempotent re-run; user may personalize afterwards; failure of one widget definition does not block the rest; marks onboarding step complete
- [ ] T026 [US4] Implement `DB/starter/service.py` (`StarterService.apply`, `starter_applied_at`) wired to the 002 onboarding step and `dashboard.starter_applied` event; frontend onboarding step screen reusing the dashboard preview

## Phase 8: US5 — Since Last Login summary (P2)
- [ ] T027 [P] [US5] Write `backend/tests/integration/dashboard/test_since_last_login.py`: aggregates provider items since boundary; permission-scoped per principal; another user's private data never appears (conformance kit); empty ⇒ state with next action; boundary advances only on `seen`; two concurrent sessions don't lose items; lookback cap
- [ ] T028 [US5] Implement `DB/summary/aggregator.py` (parallel providers with timeout, rank by priority+recency, cap), routers `GET /dashboard/since-last-login`, `POST …/seen`, and `FD/summary/SinceLastLoginCard.tsx`
- [ ] T029 [US5] Implement first `ChangeSummaryProvider`s for services state changes (006) and a provider conformance test helper `backend/tests/contract/dashboard/provider_kit.py` for domain specs

## Phase 9: US6 — Marketplace-provided widgets (P2)
- [ ] T030 [P] [US6] Write `backend/tests/integration/dashboard/test_declarative_widgets.py`: plugin/marketplace widget registers with a template and data source → appears in catalog immediately; same states/policies/permissions as first-party; failing widget isolated; config JSON Schema blocks script/markup injection; deactivation ⇒ placeholder, config retained and restored on reactivation
- [ ] T031 [US6] Implement declarative templates `FD/templates/{Stat,List,Chart,Timeline,Status}.tsx` and `DB/registry/plugin_widgets.py` (register/unregister on `plugin.state_changed`; namespaced keys; placeholder state)

## Phase 10: US7 — Responsive layouts (P2)
- [ ] T032 [P] [US7] Write `frontend/tests/e2e/dashboard/responsive.spec.ts`: lg/md/sm layouts; sm single column in the same order; all personalization functions reachable on mobile; 320 px reflow; reading order = DOM order = layout order
- [ ] T033 [US7] Implement `FD/grid/ResponsiveGrid.tsx` (12-col CSS grid, container queries, derived md layout, single-column sm) honoring 022 density tokens

## Phase 11: Polish & cross-cutting
- [ ] T034 [P] Implement `DB/invalidate/bridge.py` mapping registered `invalidate_on` events to `widget.invalidate {key}` SSE messages (key only; refetch re-authorizes) and frontend handler invalidating the matching query; test with duplicate events
- [ ] T035 [P] Register `dashboard` with Observability (functional probe: effective dashboard contains mandatory widgets; per-widget latency/state/timeout metrics) in `DB/observability.py`
- [ ] T036 [P] Add `/dashboard*`, `/widgets/*`, `/admin/dashboard/*` to the permission-matrix test, regenerate OpenAPI client, write `docs/dashboard-widgets.md` (how domains register widgets/providers, template catalog, policy semantics)
- [ ] T037 Run `specs/009-dashboard-widgets/quickstart.md` end-to-end; record deviations and open product confirmations (OQ-40..44 defaults)

## Dependencies & Order
Setup → Foundational → US1 (MVP) → US8 → US2 → US3 → US4 → US5 → US6 → US7 → Polish. US3 enforcement hooks into US2 writes; US4 needs US3 overlay; US6 needs registry + templates; US7 can run in parallel after US1.
**Parallel examples**: T004/T005 · T009/T010 · T016/T017 · T021/T022 · T034/T035/T036.
**MVP**: Phases 1–3 (registry, gateway with per-widget states, dashboard page with isolated frames and first widgets).

## Format validation
37 tasks, all checkbox + ID + path; story labels only on story phases.
