---
description: "Task list — Design System, Personalization, Themes & Accessibility (spec 022)"
---

# Tasks: Design System, Personalization, Themes & Accessibility

**Input**: `specs/022-personalization-themes-a11y/` · **Branch**: `022-personalization-themes-a11y` · **Roadmap**: Phase 3 step 8 · **Tests**: included.
Abbrev: **`DS/`** = `frontend/src/design-system`, **`UI/`** = `backend/src/portalab/modules/ui`. Trailer: `Co-Authored-By: Claude Code (Anthropic)`.
Prerequisites (not implemented here): `D-001` frontend scaffold + `FunctionalState` seed · `D-003` authz · `D-020` config/preferences (`/me/preferences`). Widget layout engine = 009; notification delivery = 010; locale resolution = 026 (contract only).

## Phase 1: Setup
- [ ] T001 Create `DS/{tokens,themes,components,state,a11y,sound,rtl}/`, `UI/{themes,api,models}/__init__.py`, `backend/migrations/ui/versions/`, `frontend/tests/{unit,a11y,e2e}/`
- [ ] T002 [P] Add frontend deps (`@radix-ui/*`, `class-variance-authority`, `eslint-plugin-jsx-a11y`, `@axe-core/playwright`, `axe-core`, contrast lib) in `frontend/package.json` and enable jsx-a11y rules in `frontend/biome.json`/ESLint config
- [ ] T003 [P] Declare settings (`ui.allowedThemes`, `ui.defaultTheme`, `ui.textScale.min|max`, `ui.forceReducedMotion`, user keys `ui.theme|density|textScale|contrast|reducedMotion|soundEnabled|notificationPosition|notificationDurationSeconds|notificationStyle`) in `UI/settings.py`; permission `appearance.manage` (audited) in `UI/permissions.py`

## Phase 2: Foundational — tokens, schema, validator
### Tests first
- [ ] T004 [P] Write `frontend/tests/unit/contrast.test.ts`: WCAG ratio calculation vs reference values; text 4.5:1, large/UI 3:1 thresholds; alpha/background handling
- [ ] T005 [P] Write `frontend/tests/unit/theme-schema.test.ts`: valid definition passes; unknown keys, script/URL values, missing state mapping rejected
- [ ] T006 [P] Write `frontend/tests/unit/token-lint.test.ts`: raw color literals in components fail lint
### Implementation
- [ ] T007 Implement `DS/tokens/tokens.css` + Tailwind preset mapping utilities to CSS variables (colors roles, type scale, spacing/density, radii, shadows, motion)
- [ ] T008 Implement `DS/themes/schema.ts` (`ThemeDefinition` closed schema, zod) and `DS/themes/floor.ts` (contrast floor over declared pairs, state colors, solid fallback for imagery); shared JSON Schema exported for the backend
- [ ] T009 Implement built-in themes `DS/themes/builtin/{light,dark,high-contrast}.ts` passing the floor; add custom lint rule banning raw colors outside `DS/tokens`
- [ ] T010 Implement `UI/models` + Alembic revision for `ui.themes` (seed built-ins, never deleted while referenced)

## Phase 3: US1 — Themes change appearance, never functional meaning (P1) 🎯 MVP
**Independent test**: render surfaces in all ten states across three drastically different themes; assertions on state, data and accessible name identical.
- [ ] T011 [P] [US1] Write `frontend/tests/unit/functional-state.test.tsx`: closed set of ten states; theme `state_map` changes color/icon/label only; accessible name and `data-state` identical across themes; unknown state rejected
- [ ] T012 [US1] Implement `DS/state/stateMap.ts` + `DS/state/FunctionalState.tsx` (icon + text + color, `asOf`, `onRetry`), retrofitting the 001 seed component
- [ ] T013 [US1] Implement `DS/themes/ThemeProvider.tsx` (`useTheme()`, applies tokens to `<html>`, fallback to default on failure) and `DS/themes/themeSwitch.test` coverage for data invariance
- [ ] T014 [US1] Implement `UI/themes/service.py`: persist/validate themes, floor report, enable/disable; refuse presentational themes that alter state set (spec FR-003/010)
- [ ] T015 [US1] Implement routers `GET /ui/themes`, `POST /admin/ui/themes`, `PATCH /admin/ui/themes/{id}`, `GET /admin/ui/themes/{id}/floor-report` in `UI/api/router.py` (`appearance.manage`, problem codes `theme.invalid_definition|floor_violation`)

## Phase 4: US3 — Accessibility preferences (P1)
- [ ] T016 [P] [US3] Write `frontend/tests/unit/a11y-prefs.test.tsx`: reduced motion (system + explicit) removes animation/transition while content preserved; high contrast overrides theme; text scale 0.85–2.0 reflows without clipping; admin `forceReducedMotion` wins
- [ ] T017 [US3] Implement `DS/a11y/PreferencesProvider.tsx` (`usePreferences()`, overrides applied after theme, localStorage mirror for first paint, sync with `/me/preferences`)
- [ ] T018 [US3] Implement `DS/a11y/motion.ts`, `contrast.ts`, `textScale.ts` helpers and CSS (`[data-reduced-motion]`, `[data-contrast=high]`, scale var)
- [ ] T019 [US3] Add `ui.*` preference validation (ranges, enums, allowed themes) via 020 declared keys; retain stored value when policy narrows (`UI/preferences.py`)

## Phase 5: US4 — Keyboard, touch, responsive, RTL (P1)
- [ ] T020 [P] [US4] Write `frontend/tests/a11y/keyboard.spec.ts` (Playwright): keyboard-only journey login → shell → settings; visible focus; no focus trap; shortcuts discoverable; target size ≥ 24×24; no drag-only interaction (alternative present)
- [ ] T021 [P] [US4] Write `frontend/tests/a11y/reflow.spec.ts`: 320 px width reflow, text spacing override, touch targets, mobile functional completeness on gallery
- [ ] T022 [P] [US4] Write `frontend/tests/unit/rtl.test.tsx`: `dir`/`lang` set from `LocaleContext`; logical properties; directional icons mirrored
- [ ] T023 [US4] Implement base components (Button, Link, Form fields, Dialog, Drawer, Tabs, Menu, Popover, Tooltip, Table, List) in `DS/components/` on Radix with WCAG 2.2 AA behaviours (focus appearance, target size, accessible auth input attributes)
- [ ] T024 [US4] Implement `DS/a11y/KeyboardShortcuts.ts` registry (consumed by 004/008) and `DS/rtl/DirectionProvider.tsx` + mirrored-icon list
- [ ] T025 [US4] Implement responsive layout primitives (`Stack`, `Grid`, `Container`, breakpoint hooks) and density tokens (compact/comfortable/spacious altering spacing only)

## Phase 6: US5 — Themes never hide critical information (P1)
- [ ] T026 [P] [US5] Write `frontend/tests/a11y/critical-info.spec.tsx`: for every theme × high contrast, critical states (error, unauthorized, maintenance, unavailable) remain visible with ≥ 3:1 contrast and non-color cue; hidden/low-opacity override rejected by floor
- [ ] T027 [US5] Extend `DS/themes/floor.ts` with critical-surface rules (never `display:none`, min opacity, min size) and wire the floor report into `UI/themes/service.py` rejection path with `theme.floor_violation` detail
- [ ] T028 [US5] Implement `DS/a11y/Announce.tsx` live regions (polite/assertive) used for async results and critical state changes

## Phase 7: US7 — Preference persistence (P1)
- [ ] T029 [P] [US7] Write `backend/tests/integration/ui/test_preferences_persistence.py`: preferences survive theme change, device change (second session), and a simulated upgrade with removed option (sensible migration); no secrets in change events
- [ ] T030 [US7] Implement `UI/preferences.py` upgraders for renamed/removed options and `UI/events.py` registering `theme.changed`, `theme.policy_changed`, `accessibility.preference_changed` (dedup `(user_id, key, change_seq)`)
- [ ] T031 [US7] Implement frontend preference sync, conflict handling (last-write by `change_seq`) and fallback when a preferred theme is disabled (preference retained)

## Phase 8: US2 — Layout & density personalization within policy (P1)
- [ ] T032 [P] [US2] Write `frontend/tests/unit/policy-bounds.test.tsx`: mandatory/locked/disabled/conditional policy states shown with explanation; user choices retained when policy relaxes; density never changes functional content
- [ ] T033 [US2] Implement `DS/components/PolicyField.tsx` (locked/mandatory/disabled display) and expose `layoutPresets` preference contract for 009 (no widget engine here)

## Phase 9: US6 — Notification appearance & sound (P2)
- [ ] T034 [P] [US6] Write `frontend/tests/unit/sound-notification.test.tsx`: sound-off honored, reduced motion removes toast animation, no autoplay before gesture, meaning (severity icon+text) unchanged by style/position
- [ ] T035 [US6] Implement `DS/sound/SoundService.ts` and `DS/components/Notification.tsx` (position, duration, style from prefs/theme; consumed by 010)

## Phase 10: US8 — Theme capability bounds (P2)
- [ ] T036 [P] [US8] Write `backend/tests/security/ui/test_theme_inert.py`: themes containing scripts/external URLs/unknown keys rejected; theme registration requires `appearance.manage`; enabling an external (marketplace-sourced) theme audited; theme cannot affect permissions or data
- [ ] T037 [US8] Implement `allowedThemes` policy enforcement in `GET /ui/themes` and preference validation; audit sensitive enable/disable via `AuditSink`

## Phase 11: Polish & cross-cutting
- [ ] T038 [P] Implement remaining catalog components (Card, Panel, Badge, Progress, Timeline, Calendar, Chart wrapper, Avatar, Media/Service/User/Achievement/Project cards) in `DS/components/` with state docs, incrementally as consumers need them
- [ ] T039 [P] Build dev-only component gallery route `frontend/src/features/dev/gallery` showing every component × state × theme; wire `npm run test:a11y` (axe on gallery + key routes) into CI `test` stage in `.gitlab-ci.yml`
- [ ] T040 [P] Add `/ui/*` routes to the permission-matrix test and OpenAPI client regeneration; write `docs/design-system.md` (tokens, theme authoring, floor rules, WCAG 2.2 checklist)

## Cross-spec obligations (audit 2026-10-01 — see `decisions/PLAN_FOLLOWUPS.md`)
- [ ] T041 Add user preference `ui.campaignThemes` (`allow|ignore`) and the campaign theme overlay in `DS/themes/ThemeProvider.tsx` (overlay only if allowed by policy and preference; accessibility preferences still win); theme availability for Marketplace theme products reads 015 `EntitlementReader`; test `frontend/tests/unit/campaign-overlay.test.tsx` (F8)
- [ ] T042 [P] Expose owner-tagged registration on the theme registry: `register(..., owner="module:<id>|plugin:<key>")` and `unregister(owner)`, with a test in `backend/tests/unit/ui/test_registry_owner.py` proving all contributions of an owner disappear (required by 023's conformance sweep, F20)

- [ ] T043 Run `specs/022-personalization-themes-a11y/quickstart.md` end-to-end and record deviations

## Dependencies & Order
Setup → Foundational → US1 (MVP) → US3 → US4 → US5 → US7 → US2 → US6 → US8 → Polish. US3/US4 may run in parallel after US1; US5 needs the floor from Foundational; US7 needs 020 preferences; US2 depends on policy keys from T003.
**Parallel examples**: T004/T005/T006 · T011 with T016 · T020/T021/T022 · T038/T039/T040.
**MVP**: Phases 1–3 (tokens, schema/floor, functional-state mapping, theme switch, theme API).

## Format validation
43 tasks, all checkbox + ID + path; story labels only on story phases.
