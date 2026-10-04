# Implementation Plan: Visual Experience (Default Theme, Header, Grouped Navigation, Layout-Capable Themes)

**Branch**: `027-visual-experience` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/027-visual-experience/spec.md`

## Summary

Re-compose the portal's presentation on top of the implemented specs: a personal header (avatar, level/XP,
Coins, notifications, search, assistant, menu) fed independently by existing endpoints and a new live
`progression.changed` event; navigation promoted from flat groups to registered **sections** (≤ 9,
Administration grouped by topics, personal pages in the avatar menu); phone/tablet/desktop frames chosen
from the theme's **layout profile**; a design-system page kit (PageHeader, Card, Tile, ListItem, Skeleton,
EmptyState, Avatar, Level/Coin badges, Celebration) adopted by every module page; a new default theme
family `portalab` (media-center direction, dark by default) with theme schema **v2** (layout, motion,
celebration, extended sounds, families); and a 2D dashboard editor (drag, resize handles, gallery, keyboard
path) backed by `x,y` coordinates, a shared deterministic placement/compaction engine and a data migration.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.9 on Node 22 (frontend)
**Primary Dependencies**: existing FastAPI/Pydantic/SQLAlchemy/Alembic; React 19, TanStack Query, React
Router, Radix UI, Tailwind 4 (CSS-variable tokens), react-intl, zod. **New (frontend only)**:
`lucide-react` (icons, R15), `@fontsource-variable/inter` and `@fontsource-variable/plus-jakarta-sans`
(self-hosted fonts, R16). No grid/drag/animation library (R10, R12, R17).
**Storage**: PostgreSQL — `dashboard.widget_instances` gains `x`, `y` (migration `dashboard_0002`); theme
documents v2 in `ui` (data migration upgrading built-ins + seeding `portalab-dark/-light`); new user-tier
settings in Administration config. No new table.
**Testing**: pytest (unit/integration/migrations/contract), Vitest + Testing Library + axe, Playwright
(e2e + a11y at 3 widths × built-in themes)
**Target Platform**: self-hosted Linux container; evergreen browsers on phone, tablet, desktop
**Project Type**: web application (backend + SPA)
**Performance Goals**: theme switch applies < 1 s without reload; header live update within the normal
SSE delay (≤ ~3 s); drag/resize preview at 60 fps on desktop (engine O(n²) with n ≤ ~40 widgets); first
paint of the frame unchanged vs today (fonts preloaded, icons tree-shaken).
**Constraints**: themes stay inert data (no CSS/JS); WCAG 2.2 AA on every built-in theme × device class;
reduced motion / sound-off / high contrast always override; no permission or business change; plugins only
use the design-system export surface; disk-light Docker image (fonts/sounds < 1 MB total).
**Scale/Scope**: ~45 routed pages across 25 feature folders re-composed; ~55 navigation contributions
re-assigned; 5 built-in themes; dashboards ≤ ~40 widgets per user.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] I. Product Integrity — PASS: presentation-only; no business rule touched; spec gap (no header/nav design in docs) surfaced in spec.
- [x] II. Modular Architecture — PASS: sections live in `capabilities.navigation`; gamification publishes its own live event; header composes module endpoints client-side, no cross-module imports.
- [x] III. Extensibility First — PASS: plugins declare sections/topics through the existing contribution path; plugin themes use v2 through the 022/023 pipeline; withdrawal sweeps sections.
- [x] IV. Event-Driven Domain — PASS: `progression.changed` emitted inside the ledger transaction via the outbox; client dedups by `seq`.
- [x] V. Source of Truth & Data Integrity — PASS: dashboard migration back-fills coordinates without losing instances/config (SC-012); theme v1 upgraded on read, never rewritten destructively.
- [x] VI. Security & Authorization — PASS: navigation filtering and dashboard policy remain server-side; arrangement validated server-side; live event audience = owner.
- [x] VII. Privacy by Design — PASS: header shows own data only; no new exposure of other users.
- [x] VIII. Testability & Quality — PASS: SC-001…012 mapped to automated tests (quickstart), hallway tests for SC-005/011.
- [x] IX. Resilience & Graceful Degradation — PASS: each header element and section render independently; degraded navigation unchanged.
- [x] X. UX Consistency — PASS: the page kit + lint check enforce one composition; EmptyState requires an action.
- [x] XI. Functional State vs Presentation — PASS: layout/motion/sound are presentation; functional states unchanged; accessibility overrides last.
- [x] XII. Accessibility — PASS: keyboard path for every drag/resize, touch-first bottom bar, reduced motion/transparency, floor per device class.
- [x] XIII. Observability & Auditability — PASS: theme/policy changes keep 022 audit; navigation section rejections recorded as diagnostics; no new sensitive action.
- [x] XIV. Deterministic Business Rules — N/A (no rule change); placement engine deterministic.
- [x] XV. Internal Economy Integrity — PASS: Coins displayed read-only; no transaction path added.
- [x] XVI. AI Safety & Boundaries — N/A (assistant entry only moves).
- [x] XVII. Search and AI Independence — PASS: search and assistant are separate header elements.
- [x] XVIII. Configuration Hierarchy — PASS: new prefs are user-tier settings under admin policy (allowed themes, forced motion, default theme).
- [x] XIX. Versioning & Evolution — PASS: `groups` alias and `PUT /dashboard/layout` kept one release; theme v1 accepted.
- [x] XX. Simplicity & Maintainability — PASS: no new backend dependency; frontend adds icons + fonts only; no duplicate navigation/theme mechanisms.

Post-design re-check (after Phase 1): unchanged — all PASS; no Complexity Tracking entry.

## Project Structure

### Documentation (this feature)

```text
specs/027-visual-experience/
├── plan.md
├── research.md          # R1–R23
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api-contracts.md
│   └── ui-contracts.md
├── checklists/requirements.md
└── tasks.md             # /speckit.tasks
```

### Source Code (repository root)

```text
backend/src/portalab/
├── capabilities/navigation/
│   ├── contribution.py          # + optional `topic`
│   ├── sections.py              # NEW NavigationSection + register_section / registry
│   └── __init__.py
├── modules/shell/
│   ├── builtin.py               # built-in sections + re-assigned groups/topics (R3)
│   ├── assembler/assembler.py   # sections/topics/personal/direct; `groups` alias
│   ├── assembler/layout.py      # section-aware ordering
│   ├── settings.py              # shell.navigation.expanded, shell.welcome.dismissedAt
│   └── api/router.py            # layout API: sections, section_labels
├── modules/dashboard/
│   ├── arrangement.py           # NEW validation + collision + compaction (Python port of engine)
│   ├── models/__init__.py       # x, y columns
│   ├── service/…                # arrangement(), add at first free, derived position
│   └── api/router.py            # PUT /dashboard/arrangement, x/y in GET/PATCH/POST, starter x/y
├── modules/gamification/
│   └── ledger/… (+ live.py)     # publish_live("progression.changed") in the ledger transaction
├── modules/ui/
│   ├── themes/definition.py     # v2 mirror + v1 upgrade
│   ├── themes/theme.schema.json # regenerated from zod
│   ├── themes/builtin/*.json    # portalab-dark, portalab-light, upgraded light/dark/high-contrast
│   └── settings.py              # ui.colorMode, default theme portalab-dark
└── migrations/
    ├── dashboard/versions/…_dashboard_0002_arrangement.py
    └── ui/versions/…_ui_0002_theme_v2.py

backend/tests/
├── unit/{navigation,dashboard,ui}/…           # sections, engine parity fixtures, theme v2
├── integration/{shell,dashboard,gamification,ui}/…
└── migrations/test_dashboard_0002.py

frontend/src/
├── design-system/
│   ├── components/{PageHeader,Card,Tile,ListItem,Avatar,Badges,StatFigure,Skeleton,EmptyState,Icon,AuthLayout}.tsx
│   ├── feedback/Celebration.tsx               # + useCelebrate
│   ├── themes/{schema,apply,floor,ThemeProvider}.ts(x)   # v2, families, data-* attributes
│   ├── themes/builtin/{portalab-dark,portalab-light,…}.json
│   ├── tokens/tokens.css                      # new scale, elevation, glass, motion profiles
│   ├── sound/SoundService.ts                  # reward, levelUp, ui
│   └── index.ts                               # export surface for plugins
├── shell/
│   ├── AppShell.tsx                           # NavFrame + AppHeader + PageFrame
│   ├── header/{AppHeader,PersonalMenu,ProgressChip,useHeaderData}.tsx
│   ├── nav/{NavFrame,SectionNav,Sidebar,TopBar,Rail,BottomBar,Drawer}.tsx
│   └── shell.css
├── features/dashboard/
│   ├── grid/{engine.ts,DashboardGrid.tsx}
│   ├── edit/{EditSession.ts,DragLayer.tsx,KeyboardArrange.tsx,WidgetGallery.tsx}
│   └── WelcomeCard.tsx
├── features/*/…                               # pages migrated to PageHeader + kit
└── features/auth/…                            # AuthLayout
frontend/public/assets/sounds/portalab/*.wav   # generated by scripts/gen-sounds.mjs
frontend/scripts/{check-page-header.mjs,gen-sounds.mjs}
frontend/tests/{unit,a11y,e2e/visual-experience}/…
tests/fixtures/dashboard-arrangements.json     # shared engine parity cases (backend + frontend)
```

**Structure Decision**: existing web-application layout (backend modules + SPA). Work is mostly frontend
(shell, design system, every feature page); backend changes are additive in `capabilities.navigation`,
`shell`, `dashboard`, `gamification` (live event) and `ui` (theme v2), plus two migrations. The shared
engine fixtures live at the repository's `portalab/tests/fixtures/` so both test suites read the same cases.

## Delivery slices (for /speckit.tasks)

1. **Foundation**: tokens/fonts/icons, theme v2 schema + upgrade + families + `ui.colorMode`, `portalab`
   theme family, page kit components, Celebration + sounds.
2. **US1 Header** (P1): header components, independent queries, live `progression.changed`.
3. **US2 Sections** (P1): sections capability, assembler, built-in re-assignment, SectionNav, personal menu.
4. **US3 Responsive frames** (P1): NavFrame variants (sidebar/rail/bottom bar/drawer/top bar), state
   preservation, 320 px reflow.
5. **US4 Page composition** (P2): migrate every feature page to the kit; lint check; skeletons/empty states.
6. **US6 Dashboard editor** (P2): engine (TS + Python parity), migration, arrangement API, editor, gallery,
   keyboard path, derived views.
7. **US5 Layout-capable themes** (P2): layout/motion/sound attributes honored by every frame/component,
   theme switch preserving state, floor per device class, admin/plugin theme v2 validation.
8. **US7 Sign-in & welcome** (P3), then polish: a11y sweep, docs (`docs/design-system.md`,
   `docs/navigation-contributions.md`, `docs/dashboard-widgets.md`), OpenAPI/client regeneration.

## Complexity Tracking

No constitution violations — section intentionally empty.
