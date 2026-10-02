---
description: "Task list — Portal Core: Global Shell & Navigation (spec 004)"
---

# Tasks: Portal Core — Global Shell & Navigation

**Input**: `specs/004-portal-core-shell/` · **Branch**: `004-portal-core-shell` · **Roadmap**: Phase 3 step 9 · **Tests**: included.
Abbrev: **`SH/`** = `backend/src/portalab/modules/shell`, **`FE/`** = `frontend/src/shell`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` capability registry + SSE kernel · `D-002/003` principal + `authorize()` + `/me/permissions` · `D-020` config/toggles/preferences · `D-022` design system (`FunctionalState`, `Announce`, shortcut registry). Search (008), AI (018), notifications (010) are slot contracts until they land; health summary (006/025) feeds the banner.

## Phase 1: Setup
- [X] T001 Create `backend/src/portalab/capabilities/navigation/__init__.py`, `SH/{assembler,api,models,validator}/__init__.py`, `backend/migrations/shell/versions/`, `FE/{router,nav,breadcrumbs,palette,shortcuts,status,slots}/`, `backend/tests/{unit,integration,security}/shell/`, `frontend/tests/{unit,e2e}/shell/`
- [X] T002 [P] Add `react-router` dependency and configure data-router + lazy route loading in `frontend/package.json`, `FE/router/index.tsx`
- [X] T003 [P] Declare settings (`shell.navigation.layout`, `shell.navigation.allowUserOrdering`, `shell.shortcuts.defaults`, user `shell.navigation.userOrder|shortcuts|sidebarCollapsed`) in `SH/settings.py`; permission `shell.manage` (audited) in `SH/permissions.py`

## Phase 2: Foundational — contribution model & registry
### Tests first
- [X] T004 [P] Write `backend/tests/unit/shell/test_contribution_schema.py`: closed schema; unknown fields, missing permission, non-namespaced plugin key, duplicate key rejected; `schema_version` upgrader hook
- [X] T005 [P] Write `backend/tests/unit/shell/test_ordering.py`: precedence admin layout > user order (when allowed) > manifest hint; deterministic tie-break `(order_hint, priority, key)`; conflicting contributions resolve identically on repeated runs
### Implementation
- [X] T006 Implement `capabilities/navigation/contribution.py` (`NavigationContribution` Pydantic model, closed schema) and `registry.py` (`register_contribution`, duplicate detection, namespace rules)
- [X] T007 Implement `SH/models` + Alembic revision for `shell.contribution_errors`; `SH/validator/isolator.py` recording rejected/failing contributions with count aggregation (no personal data)
- [X] T008 Implement ordering/grouping resolver `SH/assembler/layout.py` per T005

## Phase 3: US2 — Dynamic, rights-aware navigation (P1) 🎯 MVP
**Independent test**: toggle a module and change a user's role; navigation reflects both without manual reconfiguration.
- [X] T009 [P] [US2] Write `backend/tests/integration/shell/test_assembler_permissions.py`: permission matrix per entry (granted/denied/no-grant default-deny); disabled module/plugin ⇒ entries absent; hidden entries never leak names in response; authz failure ⇒ minimal safe nav, never more rights
- [X] T010 [P] [US2] Write `backend/tests/integration/shell/test_epochs_cache.py`: cache keyed by `(principal, permission_epoch, module_epoch)`; role change/module toggle invalidates; ETag 304 behaviour
- [X] T011 [P] [US2] Write `backend/tests/integration/shell/test_contribution_isolation.py`: malformed or raising contribution dropped with diagnostic, remaining nav intact
- [X] T012 [US2] Implement `SH/assembler/assembler.py` (`NavigationAssembler.build`) with enablement check, batched `authorize()`, layout, caching and fail-closed fallback
- [X] T013 [US2] Implement routers `GET /me/navigation` (ETag) in `SH/api/router.py` and register first-party contributions for existing modules (Home, Admin, Profile) via `register_contribution`
- [X] T014 [US2] Implement epoch bump consumers for `permission.*` (003), `admin.module_toggled|plugin_toggled` (020), `plugin.state_changed` in `SH/assembler/epochs.py`; emit `navigation.contribution_rejected` diagnostic event
- [X] T015 [US2] Implement `GET /me/stream` SSE (`navigation.changed`, heartbeat) and `GET/PUT /admin/shell/layout`, `GET /admin/shell/contribution-errors` (`shell.manage`, audited)

## Phase 4: US1 — Persistent shell, one environment (P1)
- [X] T016 [P] [US1] Write `frontend/tests/unit/shell/appshell.test.tsx`: shell slots present on every route; route change keeps shell mounted and preserves state; landmarks (header/nav/main) and skip-link
- [X] T017 [US1] Implement `FE/AppShell.tsx` with slots (`Header`, `PrimaryNav`, `SearchEntry`, `AiEntry`, `NotificationEntry`, `IdentityMenu`, `Outlet`, `GlobalStatusBanner`) using design-system components
- [X] T018 [US1] Implement `FE/nav/NavigationProvider.tsx` (TanStack Query for `/me/navigation`, SSE invalidation, refetch on focus/reconnect) and `PrimaryNav.tsx` rendering groups/entries/badges with functional states
- [X] T019 [US1] Implement authenticated-only guard (login redirect, no shell for anonymous) in `FE/router/guards.tsx`; service/external data shown as integrated portal content (no raw outbound link patterns lint)

## Phase 5: US7 — Global states: loading, error, degraded, unauthorized (P1)
- [X] T020 [P] [US7] Write `frontend/tests/unit/shell/route-boundary.test.tsx`: loading/error/unavailable/unauthorized/not-available rendering; existence-sensitive routes render identical output for forbidden and missing; slow region does not block unrelated navigation
- [X] T021 [P] [US7] Write `frontend/tests/e2e/shell/degraded.spec.ts`: multiple areas failing ⇒ banner; navigation, search entry and palette remain operable; chunk-load failure isolated with retry
- [X] T022 [US7] Implement `FE/router/RouteBoundary.tsx` (error/suspense boundaries, `FunctionalState`) and `RouteHandle` typing (`crumb`, `related`, `existenceSensitive`, `requiredPermission`)
- [X] T023 [US7] Implement `FE/status/GlobalStatusBanner.tsx` consuming the health summary endpoint (stub until 006/025 API wired) and degraded-mode behaviour; disabled/unauthorized destination handling for direct URLs

## Phase 6: US4 — Search and AI reachable everywhere (P1)
- [X] T024 [P] [US4] Write `frontend/tests/unit/shell/slots.test.tsx`: Search and AI entries rendered on every page; AI absence/outage shows degraded entry while search works; entries hidden/disabled per permission without leaking
- [X] T025 [US4] Implement `FE/slots/SearchEntry.tsx` and `AiEntry.tsx` with `SearchProvider`/`AiProvider` contracts (placeholder providers until 008/018) and independent error isolation

## Phase 7: US5 — Command Palette & keyboard shortcuts (P2)
- [X] T026 [P] [US5] Write `frontend/tests/unit/shell/shortcuts.test.tsx`: baseline catalog (`Mod+K`, `/`, `g`-chords, `?`, `Esc`); inactive in inputs; user customization persisted; conflict detection
- [X] T027 [P] [US5] Write `frontend/tests/e2e/shell/palette.spec.ts`: opens from any page, lists only permitted commands, keyboard-only selection, focus returns to trigger on close, screen-reader announcements
- [X] T028 [US5] Implement `FE/palette/CommandRegistry.ts`, `CommandPalette.tsx` (Radix Dialog + accessible listbox, fuzzy match) and `FE/shortcuts/ShortcutManager.ts` + help overlay; `commands[]` taken from `NavigationView`

## Phase 8: US3 — Orientation: breadcrumbs & contextual navigation (P2)
- [X] T029 [P] [US3] Write `frontend/tests/unit/shell/breadcrumbs.test.tsx`: hierarchy from route handles with async label resolvers, navigable ancestors, truncation accessible; empty states always offer a next action
- [X] T030 [US3] Implement `FE/breadcrumbs/Breadcrumbs.tsx`, `RelatedLinks.tsx` and `EmptyState` with mandatory next-action prop (no dead end)

## Phase 9: US6 — Responsive & mobile-complete navigation (P2)
- [X] T031 [P] [US6] Write `frontend/tests/e2e/shell/mobile.spec.ts`: 360 px viewport shows drawer with the same destination set as desktop; search/AI/palette reachable; touch targets ≥ 24 px; keyboard/touch parity
- [X] T032 [US6] Implement responsive layout (rail/sidebar/drawer) in `FE/nav/ResponsiveNav.tsx` honoring `shell.sidebarCollapsed` and density tokens

## Phase 10: Polish & cross-cutting
- [X] T033 [P] Write `backend/tests/security/shell/test_no_enumeration.py`: `/me/navigation` for different principals never exposes unauthorized entry labels; SSE payload carries only version
- [X] T034 [P] Register `shell` component with Observability (functional check: assembler builds for a probe principal), add metrics (assembly latency, cache hit ratio, rejected contributions) in `SH/observability.py`
- [X] T035 [P] Add `/me/navigation`, `/me/stream`, `/admin/shell/*` to the permission-matrix test, regenerate the OpenAPI client, update `docs/navigation-contributions.md` (how modules/plugins contribute)

## Cross-spec obligations (audit 2026-10-01 — see `decisions/PLAN_FOLLOWUPS.md`)
- [X] T036 Extend `NavigationContribution(kind=command)` with `sensitivity` and `confirmation_required` (008), and add the help-entry slot fed by 011 `HelpResolver` in `FE/slots/HelpEntry.tsx` (F17)
- [X] T037 [P] Expose owner-tagged registration on the navigation contribution registry: `register(..., owner="module:<id>|plugin:<key>")` and `unregister(owner)`, with a test in `backend/tests/unit/shell/test_registry_owner.py` proving all contributions of an owner disappear (required by 023's conformance sweep, F20)

- [X] T038 Run `specs/004-portal-core-shell/quickstart.md` end-to-end and record deviations

## Dependencies & Order
Setup → Foundational → US2 (MVP) → US1 → US7 → US4 → US5 → US3 → US6 → Polish. US1 needs the T013 API; US5 needs navigation `commands[]`; US7 independent of US2 backend after T017; US3/US6 parallel after US1.
**Parallel examples**: T004/T005 · T009/T010/T011 · T020/T021 · T026/T027 · T033/T034/T035.
**MVP**: Phases 1–4 (contribution registry, assembler/API with permission filtering and live updates, persistent shell and nav).

## Format validation
38 tasks, all checkbox + ID + path; story labels only on story phases.
