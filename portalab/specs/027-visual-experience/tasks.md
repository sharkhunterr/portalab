---
description: "Task list for 027 — Visual Experience"
---

# Tasks: Visual Experience (Default Theme, Header, Grouped Navigation, Layout-Capable Themes)

**Input**: Design documents from `/specs/027-visual-experience/`
**Prerequisites**: plan.md, spec.md, research.md (R1–R23), data-model.md, contracts/api-contracts.md,
contracts/ui-contracts.md, quickstart.md

**Tests**: Included — the constitution (VIII) requires every acceptance criterion to be test-verifiable, and
quickstart.md maps SC-001…SC-012 to automated checks.

**Organization**: grouped by user story (spec priorities: US1–US3 P1, US4–US6 P2, US7 P3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1…US7 from spec.md
- Paths are relative to `portalab/` (backend in `backend/`, SPA in `frontend/`)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: dependencies, assets and shared fixtures.

- [X] T001 Add `lucide-react`, `@fontsource-variable/inter` and `@fontsource-variable/plus-jakarta-sans` to `frontend/package.json` (npm install, lockfile updated) and import the two fonts once in `frontend/src/main.tsx` (R15, R16)
- [X] T002 [P] Write `frontend/scripts/gen-sounds.mjs` (synthesizes short WAV tones: notification, alert, success, reward, levelUp, ui) and generate `frontend/public/assets/sounds/portalab/*.wav` (< 200 kB total); add an `npm run gen:sounds` script (R18)
- [X] T003 [P] Create shared engine parity cases `tests/fixtures/dashboard-arrangements.json` (place/move/resize/compact/firstFree/derive inputs and expected outputs, ≥ 20 cases incl. overlaps, edges, size limits) (R10)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: theme v2, tokens and the design-system kit every story renders with.

**⚠️ CRITICAL**: no user-story work starts before this phase is complete.

- [X] T004 Extend the theme zod schema to v2 in `frontend/src/design-system/themes/schema.ts`: `schemaVersion` 1|2, `family`, `layout` (nav per device class incl. `orbit`, header, `headerPosition` top|bottom, cards, content, corners, widgetFrame), `motion.profile`/`motion.celebration`, `sounds` keys `notification|alert|success|reward|levelUp|ui`, `colors.accentAlt`, `colors.rarity`; add `upgradeTheme()` filling v1 defaults (data-model §5)
- [X] T005 [P] Unit tests for v2 parsing, unknown-value refusal with JSON path, and v1 → v2 upgrade defaults in `frontend/tests/unit/theme-schema-v2.test.ts`
- [X] T006 Regenerate `backend/src/portalab/modules/ui/themes/theme.schema.json` from the zod schema (`UPDATE_THEME_SCHEMA=1 npx vitest run tests/unit/theme-schema.test.ts`) and mirror v2 + v1 upgrade in `backend/src/portalab/modules/ui/themes/definition.py`
- [X] T007 Extend the accessibility floor for `accentAlt`, `rarity.*` and glass surfaces evaluated with the solid `surfaceRaised` fallback in `frontend/src/design-system/themes/floor.ts` and `backend/src/portalab/modules/ui/themes/definition.py` (R9)
- [X] T008 [P] Backend tests for v2 validation, upgrade on read and floor report (`theme.invalid`, `theme.floor_violation`) in `backend/tests/unit/ui/test_theme_v2.py`
- [X] T009 Author built-in themes `portalab-dark.json` (default, family `portalab`) and `portalab-light.json` and upgrade `light/dark/high-contrast` to v2 in `frontend/src/design-system/themes/builtin/` and their backend copies `backend/src/portalab/modules/ui/themes/builtin/` (media-center direction, accent + gamification accent + rarity palette, glass cards, playful-but-subtle motion, sound set `asset:portalab/*.wav`)
- [X] T010 Migration `backend/migrations/ui/versions/20261004_0900_ui_0002_theme_v2.py`: upsert the two `portalab-*` built-ins, upgrade stored built-ins to v2, set `ui.defaultTheme` default to `portalab-dark` unless explicitly configured
- [X] T011 Declare user-tier `ui.colorMode` (`dark|light|system`, default `dark`) in `backend/src/portalab/modules/ui/settings.py` and resolve family + color mode in `frontend/src/design-system/themes/ThemeProvider.tsx` (system ⇒ `prefers-color-scheme`; missing stored theme ⇒ default) (R8)
- [X] T012 Apply v2 in `frontend/src/design-system/themes/apply.ts` and `firstPaint.ts`: CSS variables + `data-nav-desktop|tablet|phone`, `data-header`, `data-cards`, `data-content`, `data-corners`, `data-widget-frame`, `data-motion`, `data-celebration`, `data-color-scheme` on `<html>`; accessibility overrides applied last (ui-contracts §Theme application)
- [X] T013 [P] Rewrite `frontend/src/design-system/tokens/tokens.css`: type scale with the two fonts, spacing, radii per `data-corners`, elevation levels, glass surface (with `@supports`/`prefers-reduced-transparency`/high-contrast fallback), motion durations/easings per `data-motion`, rarity and gamification tokens
- [X] T014 [P] `Icon` component mapping stable names to lucide icons (unknown ⇒ dot) in `frontend/src/design-system/components/Icon.tsx` + unit test `frontend/tests/unit/icon.test.tsx`
- [X] T015 [P] `Avatar` (image → initials with stable hue from user id), `LevelBadge`, `ProgressBar`, `CoinBadge` (compact ≥ 10 000, exact value in accessible name) in `frontend/src/design-system/components/Avatar.tsx` and `Badges.tsx` + tests `frontend/tests/unit/avatar-badges.test.tsx`
- [X] T016 [P] `PageHeader`, `Card` (variant from `data-cards`), `Tile`/`TileGrid` (artwork with gradient+icon fallback), `ListItem`, `StatFigure` in `frontend/src/design-system/components/{PageHeader,Card,Tile,ListItem,StatFigure}.tsx` + axe tests `frontend/tests/a11y/page-kit.test.tsx`
- [X] T017 [P] `Skeleton` (text/card/tile/list/figure, `aria-busy` region) and `EmptyState` (icon, title, message, required action) in `frontend/src/design-system/components/{Skeleton,EmptyState}.tsx` + tests `frontend/tests/unit/skeleton-empty.test.tsx`
- [X] T018 [P] Extend `frontend/src/design-system/sound/SoundService.ts` with `reward`, `levelUp`, `ui` events (still off by default, gesture-gated) + tests in `frontend/tests/unit/sound-service.test.ts`
- [X] T019 `Celebration` + `useCelebrate()` (queue of 1 with coalescing, sparkle/confetti/glow per `data-celebration`, reduced motion ⇒ static toast, plays `reward`/`levelUp` sounds) in `frontend/src/design-system/feedback/Celebration.tsx` + tests `frontend/tests/unit/celebration.test.tsx`
- [X] T020 Export the new kit from `frontend/src/design-system/index.ts` (plugin surface) and add every component to the `/dev/gallery` page in `frontend/src/features/dev/`

**Checkpoint**: theme v2 + kit ready — stories can start.

---

## Phase 3: User Story 1 - A personal header on every page (Priority: P1) 🎯 MVP

**Goal**: avatar, level + XP progress, Coins, notifications, search, assistant, menu on every page; live
updates with celebration.

**Independent Test**: quickstart scenarios 1–2 (header at 3 widths, gamification disabled, live credit,
level-up celebration, reduced motion, sounds off).

### Tests for User Story 1

- [X] T021 [P] [US1] Backend integration test: an XP/Coins ledger write publishes exactly one `progression.changed` live event with the user audience and post-transaction values, none on rollback, `level_up` true only when crossing a level, in `backend/tests/integration/gamification/test_live_progression.py`
- [X] T022 [P] [US1] Frontend unit tests for header degradation (progression 503 ⇒ chip hidden/neutral, unread-count failure ⇒ bell without count, gamification disabled ⇒ no empty space) and live cache patching in `frontend/tests/unit/app-header.test.tsx`

### Implementation for User Story 1

- [X] T023 [US1] Publish `progression.changed` via `core.live.publish_live` inside the ledger transaction in `backend/src/portalab/modules/gamification/ledger/writer.py` (payload per data-model §7; no other user's data) and register the topic where gamification declares its live/event types
- [X] T024 [P] [US1] `useHeaderData` (independent queries `/me`, `/me/progression`, `/me/notifications/unread-count`; SSE `progression.changed` patches the progression cache, dedup by `seq`, triggers `useCelebrate` on `level_up`/gains) in `frontend/src/shell/header/useHeaderData.ts`
- [X] T025 [P] [US1] `ProgressChip` (LevelBadge + XP ProgressBar with animated counter respecting reduced motion) in `frontend/src/shell/header/ProgressChip.tsx`
- [X] T026 [US1] `PersonalMenu` (Radix dropdown: profile, progression, personal entries, sign out) in `frontend/src/shell/header/PersonalMenu.tsx`
- [X] T027 [US1] `AppHeader` (menu control, brand, search bar ≥ tablet / button on phone, assistant, notifications with count, ProgressChip, CoinBadge, avatar → PersonalMenu; each data element in its own `RegionBoundary`; single compact row on phones; `data-header` variants) in `frontend/src/shell/header/AppHeader.tsx` and replace the old header in `frontend/src/shell/AppShell.tsx` + `ShellLayout.tsx`
- [X] T028 [US1] Header styles (full/compact/centered, glass on scroll, safe areas) in `frontend/src/shell/header/header.css`; strings in `backend/locales/en/shell.json` (+ `fr`)
- [X] T029 [US1] Playwright: header elements at 390/820/1440 widths on 4 pages, live credit animates, level-up celebrates once, reduced motion ⇒ toast only, in `frontend/tests/e2e/visual-experience/header.spec.ts` (extend the stub API in `frontend/tests/a11y/support.ts` with progression + SSE event)

**Checkpoint**: header complete and independently testable.

---

## Phase 4: User Story 2 - Navigation grouped in clear sections (Priority: P1)

**Goal**: ≤ 9 named sections with icons, Administration grouped by topics, personal pages in the avatar menu.

**Independent Test**: quickstart scenarios 3–4.

### Tests for User Story 2

- [X] T030 [P] [US2] Unit tests for section registry (closed schema, duplicates, plugin namespace, owner withdrawal) in `backend/tests/unit/navigation/test_sections.py`
- [X] T031 [P] [US2] Integration tests for `GET /me/navigation` sections: admin ≤ 9 / user ≤ 8 sections, empty sections omitted, `direct` single-entry sections, admin topics, `personal` list, unknown section ⇒ owner default ⇒ `more` + diagnostic, `groups` alias still present, degraded on authz failure, in `backend/tests/integration/shell/test_sections_view.py`

### Implementation for User Story 2

- [X] T032 [US2] `NavigationSection` model + `register_section`/`SectionRegistry` (+ `unregister(owner)`) in `backend/src/portalab/capabilities/navigation/sections.py`; export from `capabilities/navigation/__init__.py`; add optional `topic` to `NavigationContribution` in `contribution.py` (schema_version stays 1)
- [X] T033 [US2] Hook section withdrawal into the 023 contribution sweep (`Registries.remove(owner)`) in `backend/src/portalab/modules/plugins/context/registries.py`
- [X] T034 [US2] Declare built-in sections (`home, media, content, services, support, community, marketplace, admin` with topics `access, services, content, economy, system, extensions`, `me`, `more`) and re-assign every built-in contribution's `group`/`topic` per R3 in `backend/src/portalab/modules/shell/builtin.py`
- [X] T035 [US2] Section-aware assembly (sections/topics/personal/direct, empty omission, fallback + `navigation.section_unknown` diagnostic, `groups` alias) in `backend/src/portalab/modules/shell/assembler/assembler.py` and `assembler/layout.py`
- [X] T036 [US2] Admin layout API accepts section keys and `section_labels`, lists `sections` in `backend/src/portalab/modules/shell/api/router.py`; declare user settings `shell.navigation.expanded` and `shell.welcome.dismissedAt` in `backend/src/portalab/modules/shell/settings.py`
- [X] T037 [US2] Regenerate OpenAPI + client (`uv run portalab openapi -o openapi.json`, `npm run gen:api`, `npm run check:api-drift`) and update `frontend/src/shell/nav/NavigationProvider.tsx` to expose `sections` and `personal`
- [X] T038 [US2] `SectionNav` (collapsible sections with icon + label, `aria-expanded`, `direct` links, admin topic sub-headings, current entry + auto-expanded section, expansion persisted via `/me/preferences` with localStorage mirror) in `frontend/src/shell/nav/SectionNav.tsx`; wire `personal` entries into `PersonalMenu`
- [X] T039 [US2] Breadcrumbs reflect section → page in `frontend/src/shell/breadcrumbs/Breadcrumbs.tsx`; section/topic labels in `backend/locales/en/shell.json` (+ `fr`)
- [X] T040 [US2] Update the example plugin to declare a section/topic in `examples/plugins/hello/` and document sections/topics in `docs/navigation-contributions.md`
- [X] T041 [US2] Playwright: sections for admin and user, every route of the 004 route table reachable within 2 interactions, in `frontend/tests/e2e/visual-experience/sections.spec.ts`

**Checkpoint**: grouped navigation complete.

---

## Phase 5: User Story 3 - Comfortable on phone, tablet and desktop (Priority: P1)

**Goal**: phone bottom bar + drawer, tablet rail, desktop sidebar; no wasted column; state kept on resize.

**Independent Test**: quickstart scenarios 5–6.

- [X] T042 [P] [US3] `Sidebar`, `Rail` (collapsible, icon-only with labels on expand), `TopBar` variants rendering `SectionNav` in `frontend/src/shell/nav/{Sidebar,Rail,TopBar}.tsx`
- [X] T043 [P] [US3] `BottomBar` (Home, Search, Notifications badge, Menu → `Drawer` with `SectionNav`; safe-area aware) in `frontend/src/shell/nav/BottomBar.tsx`, and `OrbitNav` (floating bubble opening a radial menu of section icons, entries on an arc/list, roving focus, Escape, reduced-motion and narrow-screen half-circle fallback — R24) in `frontend/src/shell/nav/OrbitNav.tsx`
- [X] T044 [US3] `NavFrame` choosing the variant from `data-nav-*` + device class (phone < 640, tablet 640–1023, desktop ≥ 1024) without remounting the outlet; replace `ResponsiveNav` usage (removes the phone empty-column defect) in `frontend/src/shell/nav/NavFrame.tsx`, `frontend/src/shell/AppShell.tsx`, `frontend/src/shell/shell.css`
- [X] T045 [US3] `PageFrame` (content width from `data-content`, breadcrumbs, related links) in `frontend/src/shell/PageFrame.tsx`; touch targets ≥ 44 px on coarse pointers, no hover-only actions in `shell.css`
- [X] T046 [US3] Unit tests: variant choice per device class and theme, outlet not remounted on resize (form text kept) in `frontend/tests/unit/nav-frame.test.tsx`
- [X] T047 [US3] Playwright: 320/390/820/1440 widths on every route — no horizontal scroll, bottom bar on phones, rotation keeps page/scroll/text, in `frontend/tests/e2e/visual-experience/responsive.spec.ts` (extend `frontend/tests/a11y/reflow.spec.ts`)

**Checkpoint**: P1 stories (MVP) complete — header, sections and responsive frames.

---

## Phase 6: User Story 4 - A modern, consistent page composition (Priority: P2)

**Goal**: every routed page uses PageHeader + kit, skeletons and actionable empty states; dashboard greeting.

**Independent Test**: quickstart scenario 7 (`check-page-header` lint + skeleton/empty-state checks).

- [X] T048 [US4] Lint `frontend/scripts/check-page-header.mjs` (every module imported by `frontend/src/shell/router/routes.tsx` renders `PageHeader`; every `EmptyState` has an action) wired into `npm run lint`
- [X] T049 [P] [US4] Migrate home & dashboard chrome: greeting by name, "since your last visit" card, widget frames per `data-widget-frame`, skeletons in `frontend/src/features/dashboard/{DashboardPage.tsx,frame/,summary/,dashboard.css}`
- [X] T050 [P] [US4] Migrate media pages (MediaHome, CatalogPage, DetailPage with artwork hero, RequestsPage, LinksSettings, MatchingScreen) to Tile/TileGrid/PageHeader in `frontend/src/features/media/`
- [X] T051 [P] [US4] Migrate content pages (NewsPage, ArticlePage, NewsAdmin, WikiHome, PageView, PageEditor, History, CalendarPage) in `frontend/src/features/{news,wiki,calendar}/`
- [X] T052 [P] [US4] Migrate services & statistics pages (ServicesRoute, ServiceDetailRoute, StatisticsPage, WrappedStory, DefinitionsAdmin) in `frontend/src/pages/` and `frontend/src/features/statistics/`
- [X] T053 [P] [US4] Migrate support pages (IncidentsPage, IncidentConsole, MyTickets, NewTicket, TicketPage, FeedbackPage, ReviewQueue, staff Queue, admin Definitions) in `frontend/src/features/support/`
- [X] T054 [P] [US4] Migrate community & gamification pages (CommunityPage, ModerationQueue, ProgressionPage with rarity-colored achievements, leaderboards, quests, GamificationAdmin) in `frontend/src/features/{community,gamification}/`
- [X] T055 [P] [US4] Migrate marketplace pages (CatalogPage, ProductRoute, OwnedPage, ProjectsPage, ProjectRoute, MarketplaceAdmin, ProjectConsole) in `frontend/src/features/marketplace/`
- [X] T056 [P] [US4] Migrate personal pages (AccountRoute, AppearanceRoute incl. color mode selector and theme previews, LanguageSettings, NotificationCenter, NotificationPreferences, PrivacyRoute, SearchPage) in `frontend/src/pages/` and `frontend/src/features/{notifications,settings,search,appearance}/`
- [X] T057 [P] [US4] Migrate administration pages (ControlCenterRoute as topic-grouped tiles, ConfigurationRoute, RolesRoute, AuditRoute, EventsRoute, ObservabilityRoute, PrivacyAdminRoute, ServicesAdminRoute, AiAdminPage, AutomationsPage, CampaignsPage, CampaignConsole, PluginsAdmin, ModulesAdmin, PageRenderer, NotAvailablePage) in `frontend/src/pages/admin/` and `frontend/src/features/{ai,automations,campaigns,plugins,admin}/`
- [X] T058 [US4] Update existing unit/a11y/e2e tests broken by the migration (selectors via roles/labels) across `frontend/tests/` and run `npm test` + `npx playwright test`

**Checkpoint**: one composition everywhere (SC-007, SC-008).

---

## Phase 7: User Story 5 - Themes that change arrangement, motion and sounds (Priority: P2)

**Goal**: layout/motion/sound profiles honored everywhere; switching keeps state; validation for admin,
Marketplace and plugin themes.

**Independent Test**: quickstart scenarios 11–12.

- [X] T059 [P] [US5] Implement the remaining layout variants across shell and kit: `data-header-position` bottom (header as footer bar, merged with a phone bottom bar — R24), `data-header` (compact/centered), `data-cards` (flat/outlined/glass), `data-content` (narrow/full), `data-corners`, `data-motion` (none/subtle/lively/playful transitions incl. View Transitions when supported) in `frontend/src/shell/shell.css`, `frontend/src/design-system/components/components.css`, `frontend/src/design-system/tokens/tokens.css`
- [X] T060 [P] [US5] Add test-only themes `frontend/tests/fixtures/themes/{topbar-flat,rail-playful}.json` exercising every layout/motion/celebration option
- [X] T061 [US5] Appearance: theme cards with live mini-preview, family/color-mode selector, switch applied without reload in `frontend/src/features/appearance/AppearanceSettings.tsx`
- [X] T062 [US5] Unit tests: switching themes keeps open dialog, typed text and route; critical header elements present in every variant; accessibility overrides win over motion/glass/sounds in `frontend/tests/unit/theme-switch.test.tsx`
- [X] T063 [US5] Backend integration: admin `POST /admin/ui/themes/check` refuses unknown layout values (`theme.invalid` path), floor report per device class with glass fallback, plugin/Marketplace theme v2 registers disabled then enables, in `backend/tests/integration/ui/test_theme_v2_registry.py`
- [X] T064 [US5] Playwright + axe: each built-in and test theme × 3 widths on home, a list page and a form (WCAG 2.2 AA), theme switch < 1 s without reload, in `frontend/tests/e2e/visual-experience/themes.spec.ts`

**Checkpoint**: layout-capable themes complete.

---

## Phase 8: User Story 6 - Arrange the dashboard visually (Priority: P2)

**Goal**: 2D grid with drag, resize handles, gallery, keyboard path, save/cancel; derived tablet/phone views;
lossless migration.

**Independent Test**: quickstart scenarios 8–10.

### Tests for User Story 6

- [X] T065 [P] [US6] Engine unit tests reading `tests/fixtures/dashboard-arrangements.json` in `frontend/tests/unit/dashboard-engine.test.ts`
- [X] T066 [P] [US6] Python engine parity tests reading the same fixtures in `backend/tests/unit/dashboard/test_arrangement.py`
- [X] T067 [P] [US6] Migration test: ordered layouts back-filled with identical widget sets/sizes/configs, no overlaps, `x + w ≤ 12`, in `backend/tests/migrations/test_dashboard_0002.py`
- [X] T068 [P] [US6] API tests: `PUT /dashboard/arrangement` (If-Match 409, bounds/size-limit 422 with offending ids, locked/mandatory 403 with reason, compaction, `position` recomputed, omitted instances kept), `POST` first-free placement, `PATCH` x/y, deprecated `PUT /dashboard/layout` still flows, starter x/y, in `backend/tests/integration/dashboard/test_arrangement_api.py`

### Implementation for User Story 6

- [X] T069 [US6] Pure engine `place/resize/compact/firstFree/derive/readingOrder` in `frontend/src/features/dashboard/grid/engine.ts` (R10, R11)
- [X] T070 [US6] Python port with server validation (bounds, limits, policy, overlap resolution, compaction) in `backend/src/portalab/modules/dashboard/arrangement.py`
- [X] T071 [US6] Add `x`,`y` to `backend/src/portalab/modules/dashboard/models/__init__.py` and migration `backend/migrations/dashboard/versions/20261004_0910_dashboard_0002_arrangement.py` (nullable → back-fill with the engine flow → NOT NULL + check, index `(user_id, y, x)`)
- [X] T072 [US6] Service: `arrangement()` write, first-free placement on add, x/y on patch, derived `position`, starter layout with optional x/y, in `backend/src/portalab/modules/dashboard/service/` and `starter/`
- [X] T073 [US6] API: `PUT /dashboard/arrangement`, x/y in `GET/POST/PATCH`, deprecated alias, admin starter x/y in `backend/src/portalab/modules/dashboard/api/router.py`; regenerate OpenAPI + client
- [X] T074 [US6] `DashboardGrid` (explicit grid placement on desktop, derived 6-column tablet and 1–2-column phone views, DOM order = reading order) replacing `ResponsiveGrid` in `frontend/src/features/dashboard/grid/DashboardGrid.tsx` and `dashboard.css`
- [X] T075 [US6] `EditSession` (snapshot, optimistic local state, save via one PUT with If-Match, cancel restores, 409 handling) in `frontend/src/features/dashboard/edit/EditSession.ts`
- [X] T076 [US6] `DragLayer` (pointer events, capture, snapping ghost, live engine preview, edge auto-scroll, resize handles; desktop only) in `frontend/src/features/dashboard/edit/DragLayer.tsx`
- [X] T077 [US6] `KeyboardArrange` (Enter select, arrows move, Shift+arrows resize, Escape cancel, announcements) and button fallback in `frontend/src/features/dashboard/edit/KeyboardArrange.tsx` and `EditControls.tsx`; tablet/phone edit = add/hide/remove/reorder only
- [X] T078 [US6] `WidgetGallery` (preview per template or widget, description, size options, policy reasons) in `frontend/src/features/dashboard/edit/WidgetGallery.tsx`
- [X] T079 [US6] Playwright: drag, resize, gallery add, save/reload, cancel, keyboard-only path, locked reason, phone derived view, in `frontend/tests/e2e/dashboard/arrange.spec.ts`
- [X] T080 [US6] Update `docs/dashboard-widgets.md` (2D arrangement, size limits, preview for plugin widgets)

**Checkpoint**: dashboard editor complete (SC-011, SC-012).

---

## Phase 9: User Story 7 - Welcoming sign-in and first visit (Priority: P3)

**Goal**: branded sign-in/registration/recovery/first-run; dismissible welcome.

**Independent Test**: quickstart scenario 13.

- [X] T081 [P] [US7] `AuthLayout` (centered card over theme background/artwork, brand mark) in `frontend/src/design-system/components/AuthLayout.tsx`; apply to `LoginForm`, `VerifyForm`, registration/recovery and first-run screens in `frontend/src/features/auth/` and `frontend/src/features/admin/` first-run
- [X] T082 [P] [US7] `WelcomeCard` (introduces header, sections, appearance; dismiss writes `shell.welcome.dismissedAt`) in `frontend/src/features/dashboard/WelcomeCard.tsx`
- [X] T083 [US7] Tests: auth screens axe at phone/desktop, welcome shown once and not on another session after dismissal, in `frontend/tests/a11y/auth-screens.test.tsx` and `frontend/tests/e2e/visual-experience/welcome.spec.ts`

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T084 [P] Update `docs/design-system.md` (theme v2 vocabulary, families, page kit, celebrations, sounds) and `docs/extensibility.md` (plugin sections, theme v2)
- [X] T085 [P] French locale pass for all new strings in `backend/locales/fr/*.json` (catalog hygiene test green)
- [X] T086 Full verification: backend `uv run pytest -n auto --dist loadfile`, ruff/format/mypy/lint-imports; frontend lint/typecheck/test/build; Playwright alone afterwards
- [X] T087 Docker smoke (`scripts/smoke.sh`, dependencies changed) and LAN redeploy for manual hallway checks (SC-005, SC-011) per `quickstart.md`

---

## Phase 11: Shop, achievements, administration polish, theme studio (US8–US11, added 2026-10-04)

- [X] T088 [US8] Product presentation attributes (rarity, featured, poster_effect, icon; collections = categories) — model, migration, admin API, catalog API in `backend/src/portalab/modules/marketplace/`
- [X] T089 [US8] Game-style shop page: featured banner, collection and type shelves, rarity cards, animated posters, filters in `frontend/src/features/marketplace/catalog/`
- [X] T090 [US8] Product detail and admin product form with presentation fields in `frontend/src/features/marketplace/{product,admin}/`
- [X] T091 [US9] Achievement category + global unlock share and derived rarity — model, migration, API in `backend/src/portalab/modules/gamification/achievements/`
- [X] T092 [US9] Steam-like achievement list (category filter, sort by rarity, percentage, animated rare medals) in `frontend/src/features/gamification/achievements/`
- [X] T093 [US10] Services page admin entry ("Add a service") and services administration polish in `frontend/src/features/services/`, `frontend/src/features/admin/services/`
- [X] T094 [US10] Control Center as readable panel cards with states, figures and actions; wire the health panel in `frontend/src/features/admin/ControlCenter.tsx` and the overview providers
- [X] T095 [US10] News (member and admin), wiki and support (tickets, queue, admin) pages on the page kit in `frontend/src/features/{news,wiki,support}/`
- [X] T096 [US11] Theme studio: duplicate a theme, edit colors/fonts/layout/motion/sounds with live preview and floor report, publish and create the Marketplace product in `frontend/src/features/appearance/studio/`
- [X] T097 Demo data: rarities, collections (Halloween, New Wave), featured items, theme products, achievement categories in `backend/src/portalab/app/demo_seed.py`
- [X] T098 Tests (backend integration, frontend unit, Playwright) for US8–US11; dev-mode verification on the LAN instance
- [X] T099 [US10] Ship the first real connectors (Jellyfin, Plex, Seerr, Radarr, Sonarr, RomM) on a shared HTTP base, registered at start; conformance kit + mapping tests in `backend/src/portalab/connectors/`, `backend/tests/contract/connectors/`
- [X] T100 [US10] Administration kit (AdminPage, AdminSection, AdminStats, AdminTable, StatusBadge, toolbar/forms) in `frontend/src/design-system/admin/` and every administration page rebuilt on it; guided "Add a service" wizard with connector cards
- [X] T101 [US10] Service accounts ↔ members: connectors list their accounts (`service.accounts`), suggestions by e-mail then name, link/unlink/apply-all with past plays attributed, in `backend/src/portalab/modules/media/links/accounts.py` and the « Service accounts » tab of `frontend/src/features/admin/members/`
- [X] T102 [US10] Edit a member (display name, e-mail, roles, linked service accounts): `PATCH /api/v1/users/{id}` in `backend/src/portalab/modules/identity/` and `frontend/src/features/admin/members/MemberEdit.tsx`
- [X] T103 [US2] Member navigation in the hub spirit: every member section is one link whose pages are tabs, « My account » included, in `frontend/src/shell/nav/{SectionNav,HubTabs}.tsx`
- [X] T104 [US10] Connectors Tautulli (history incl. live TV, accounts), Grimmory (books/audiobooks, reading sessions, accounts), TMDB (`media.metadata`), Plex full history, Radarr/Sonarr release calendars in `backend/src/portalab/connectors/`; capabilities `media.activity_history`, `media.calendar`, `media.metadata`; `audiobook` media type
- [X] T105 [US10] Activity ingestion (backfill → incremental, attribution, catalog/work resolution, Plex/Tautulli de-duplication), daily aggregates, metadata enrichment and upcoming releases in `backend/src/portalab/modules/media/insights/` (migration `media_0002`), with export/erasure
- [X] T106 [US10] Statistics page `/media/insights` (me / whole server, categories, periods, charts, tops with posters, records, box office, members and sources for managers), enriched detail page, dashboard widgets (stats, recently added/requested, upcoming, top) in `frontend/src/features/media/` and `frontend/src/features/dashboard/widgets/media.tsx`
- [X] T107 [US10] Live progress: connector syncs report done/total (`SyncProgress.total`, `connectors.sync_state.progress`), history ingestion and TMDB enrichment report theirs (`media.task_progress`); spinner + progress bar (`LiveProgress`) on the services page and the statistics sources panel, polled while running; « Sync now » replaced by « Follow-up » for continuously read services; « Update now » / « Enrich now »
- [X] T108 [US10] Admin-only « History and metadata » page (`/admin/media-sources`, Services hub) replacing every refresh action of the member statistics page; Seerr requests keep their service author and are (re-)attributed when the account is linked; empty detail sections hidden; configurable « My statistics » widget (scope, period, category, metric, chart) with translated settings; richer declarative widget rows (thumbnail, dates, state badges, progress), services health, TMDB posters for requests and upcoming releases
- [X] T109 [US10] « My requests » after Telemetra (funnel, watched ratio, films/series, anonymous rank, over time vs previous, most watched requested, requested vs watched genres, list with posters, coming soon); Radarr/Sonarr download queues (`media.downloads`); « coming soon » widget; configurable « recently requested » widget
- [X] T110 [US8] Notifications redesign (tone colours and icons by category, badge, link, image, countdown, six styles, seven animations, chooser with preview in Appearance) with shop-sold looks enforced server-side (`marketplace.cosmetics`, product types `notification_style`/`notification_animation`); packs (`bundle` product type granting its products, admin editor, demo packs); widgets in the shop (gallery shows them locked, premium « poster wall »); readable alerts naming services; library listings up to 100 MB (Radarr)
- [X] T111 [US10] Time to availability on « My requests »: median, fastest and slowest, delays in buckets, each request placed by when it was asked compared with the release (before release, first month, first year, catalogue) against how long it took, median per moment (`RequestInsights._acquisition`, `Acquisition.tsx`)
- [X] T112 [US8] Steam-like profile looks: profile hero (banner + framed avatar), « Customise » dialog with banners, avatar frames and the film backdrop of any compatible title (one shop feature, not one product per film), designs in `design-system/themes/cosmetics.css`; product types `profile_banner`, `avatar_frame`, `profile_backdrop`, `palette`; equipped looks stored in `marketplace.equipped` (`marketplace_0004`), `GET/PUT /api/v1/me/profile-looks`, shown on community profiles; colour palettes over any theme (`ui.palette`, sold ones enforced server-side); the personal menu « Profile » opens one's community profile
- [X] T113 [US8] Shop product modal: a click on a product opens its name, type, rarity, description, price, conditions and a preview by type (notification sample in that style or replayable animation, banner, framed avatar, palette and theme colours, pack contents) with buying in place; whitelisted `preview` payload fields on products; « in the shop » links filter the shelves by type; overlays stacked above the header and decorated content
- [X] T114 [US8] Scarcity: supply per rarity set by administrators (`marketplace.rarities`, `GET/PUT /admin/marketplace/rarities`; seeded common unlimited, rare 50, epic 15, legendary 2), per-product supply override, purchase limit per period for repeatable products, minimum level (a condition, new version) — `PUT /admin/marketplace/products/{key}/availability` (`marketplace_0005`); enforced under the product row lock at acquisition (`marketplace.sold_out`, `marketplace.purchase_limit`, packs refused when a product is sold out), shown as named conditions and on products (`supply`, `remaining`, `limit_*`, `min_level`)
- [X] T115 [US8] Shop product art and sheet: cards and sheets draw a pre-rendering by type (notification in its style/animation, banner, framed avatar, palette, theme mock, badge, title, celebration, quota, widget, pack mosaic) with type and copies-left badges inside the frame; one product sheet for the modal and the page (chips, description, what you get, pack contents with a card per product and savings, facts panel: price, copies, level, limit, refund, conditions); « Close » / « Buy » footer with inline confirmation; animated poster effects removed (to be rethought)
- [X] T116 [US5] Theme schema v2 extended: heading font, case and effect; vocabulary per language (navigation, page titles, currency renamed by the universe, read by `useT`); icon overrides; backdrop patterns and animated ambient layers (`AmbientLayer`, off with reduced motion and high contrast); card styles (comic, neon, paper, pixel, terminal, ornate, hologram); celebrations (snow, bats, pixels, hearts, stars, coins, lightning, petals, bubbles); notification style and animation defaults — backend twin, shared JSON Schema; self-hosted universe fonts; per-universe sound sets (`gen:sounds`)
- [X] T117 [US2] New navigation principles chosen by themes, on phones, tablets and desktops: dock, book tabs, launcher screen, terminal line (`PrincipleNavs.tsx`), keyboard and Escape handling; miniatures show them
- [X] T118 [US5] 18 universe themes (wizardry, space opera, simulation, dune, horror, Halloween, Christmas, comic, manga, cartoon, cozy, futuristic, minimal, xeno, heroes, neowave, disco, cyberpunk) built in (`ui_0004`), built-in themes synced from their files on `portalab migrate`; e2e on phone/tablet/desktop with axe
- [X] T119 [US8] Cosmetics: ambient and celebration preferences (theme default or bought), notification looks following the theme, 12 more palettes; profile animated background, name styles, worn title and badge showcase (animated badges and titles); product types `ambient`, `profile_background`, `name_style`; « Try it » in the shop (theme, palette, ambient, celebration, notification look, never saved)
- [X] T120 [US8] Demo shop rebuilt (`demo_shop.py`, 226 products): prices by rarity, levels, copies, 18 ultimate universe packs and revised packs, more achievements, descriptions in the reader's language
- [X] T121 [US8] Celebrations drawn per effect (particles, motion and « +XP » bubble of their own) and six bubble effects: pixel rain building the bubble, burning, shattering, freezing, glitching, portal; sold-out products stay in the shop marked « Sold out »
- [X] T122 [US8] Shop for the dashboard and statistics: any existing widget sold by a `widget` product is for its owners (gallery shows it locked); widget setting values sold as `widget_option` (`<widget>:<field>=<value>`, refused server-side, shown locked in settings, `GET /dashboard/locked-options`); Media statistics sections sold as `statistic` (`media.insights.<name>`, data left out server-side, locked cards); `project_launch` product opening a community project as a proposal from the buyer's title and pitch; calendar month widget with media releases as a calendar source
- [X] T123 [US8] Shop split into departments (looks / features / packs) with shelves of eight and « see all », art drawn when near the screen, featured first then by price; coins badge and « my items » buttons removed (an « Owned » badge on the art); the shop preview plays the real celebration; rarity rebalanced (9 legendary, rare from 600 Coins, epic from 1000); Marketplace navigation opens the shop; community projects page redone (figures, launch call, stage filter, lifecycle per project); `?product=` opens a product sheet
- [X] T124 [US8] Dashboard: « Quick access » widget (`health.service_links`, each service's state and its public address — `connectors.services.public_url`, migration `connectors_0003`, set in the services admin — or its https address); daily objectives redone (count and coins on one line, reward badge per objective, done colour); shop window widget (featured then new, never owned, rarity and price); « Continue » fed by the services' history (films, episodes, books, audiobooks in progress)
- [X] T125 [US8] Media home redone (banner, scrolling rows: continue, new, recently played from the services' history — `GET /me/media/journal` — trends, recommendations, browse by kind); Statistics posters for titles outside the library (metadata provider), latest plays with posters and the right headline; Grimmory audiobook covers (`a-<id>` → `/audiobook-cover`); live TV grouped by its show (Tautulli `grandparent_title`, re-ingestion completes stored plays)
- [X] T126 [US8] Community redone (icon tabs, discovery panels with faces, timeline grouped by day with achievement names, member cards, leaderboard podium and segmented filters, proposals with a vote count and the form in a dialog, event date leaves); public campaigns page as cards (countdown, boosts, next periods); Appearance as cards showing only what the member owns with « N more in the shop » lines, theme cards without the inherited pill style; Privacy center redone (who sees what, data grouped by owner with in-place visibility, export and deletion)
- [X] T127 [US6] Dashboard grid redone: free placement on 12 / 8 / 4 columns (a dropped or resized widget stays where it was put, widgets in its way pushed down, gaps kept), « Auto fit » (pack up and to the start, widen into free space), cells shown in edit mode with free rows below, placeholder while dragging, resize from the right edge, bottom edge or corner; one layout for every screen (tablet/phone derived) or one per screen (`user_dashboards.layout_mode`, `widget_instances.views`, migration `dashboard_0003`, `PUT /dashboard/layout-mode`, `PUT /dashboard/arrangement?view=`), tablet/phone previews; widget content fits its block (no inner scrollbar: list items beyond the bottom left out and counted, posters sized to the block)
- [X] T128 [US8] Calendar: shared month grid for the widget and Discover › Calendar — a colour and an icon per kind (films, series, books, events, campaigns, maintenance, incidents, news), what lasts several days drawn as a bar across the days; incidents as a calendar source (start → resolution); media releases carry their category; widget entries with first and last day in the viewer's zone
- [X] T129 [US8] Media: « Recently added » from the services' own dates (a new episode brings its series up) and « Recent releases » (release or air date, `released` in library payloads from Plex and Grimmory) — shelves of the media home and widgets (`media.recent_releases`, kind filter)
- [X] T130 [US8] Incidents page redone (state of the portal, filter, cards with severity, steps, duration, services, latest update; timeline), incidents widget and campaigns widget as cards
- [X] T131 [US8] Communication: news desk channels (admin-defined, icon, description, newsletter on/off), article « e-mail on publish » to channel subscribers (per-channel unsubscribe in notification preferences), scheduled automatic newsletters (week's releases, recent additions, upcoming; daily/weekly/monthly) via `media.digest`; migrations news_0002, notify_0002
- [X] T132 [US8] Maintenance shown like an incident on the incidents page and optionally as a dismissible banner (health_0002); incident services chosen with a picker (whole server / services)
- [X] T133 [US10] System page redesigned (settings explorer by area with search, typed controls, reset) with SMTP/e-mail settings and portal URL
- [X] T134 [US4] Phone/tablet dashboard customization uses the grid editor on every device (drag, resize, own layout on save); only settings and remove remain on widgets
- [X] T135 [US9] Gamification administration redesigned: simple/detailed modes; overview curves (daily gains, leaders' running totals, sources); progression tuning by dragging the projected curve over members' positions (one overall pace factor, `economy.pace`); XP per action as forms (fixed + per minute, conditions, limits, presets); play streak tiers (`economy.streak`, gamification_0004); level curve and level tiers with rewards (Coins, Contribution, product offered via `marketplace.gifts`) beside shop unlocks; achievements and quests as forms
- [X] T136 [US10] Compact checkboxes everywhere (1.25rem box, the row is the touch target); CheckboxField hint under its label
- [X] T137 [US9] Campaign shop discounts (`campaigns.discounts`, best reduction per product or category, charged at purchase, struck price and campaign badge in the shop); campaign console as a form (bonuses by action, media kind, genre, title; discounts); episodes inherit their series' genres for campaign conditions
- [X] T138 [US9] Monthly quest period and optional activity window on every quest kind; weekly/monthly objective labels
- [X] T139 [US8] Feedback: form builder for feedback forms and ticket types (rating, choices…), feedback requests asked of members between two dates (one answer each, rewardable `target = request`), member page (requests, opinion kinds, my feedback with replies), staff review redesigned (status tabs, readable answers, reply with notification, request results); migration support_0003
- [X] T140 [US9] Demo/LAN economy: XP per play (count + minutes), shop purchase, ticket, feedback, request; play streak tiers; level rewards; Halloween/Christmas/cinema campaigns with genre bonuses and discounts; a year of daily/weekly/monthly/seasonal quests; a feedback request
- [X] T141 [US9] Progression page: where my XP comes from (by source with streak/campaign/pace bonuses split out, per day), current streak
- [X] T142 [US6] Dashboard: rows nobody covers are closed up outside editing; « pinned » widget policy (always there at the administrator's place, neither moved, resized, hidden nor removed) with incidents and the current campaign pinned side by side by default (banners above the grid removed; calm states when nothing runs); a fuller starter dashboard; « Default » restores it (`POST /dashboard/reset`); administration page for widget policies, pinned places and the starter
- [X] T143 [US8] Announcements through any of notification, e-mail (opt-out category) and banner (until a date, endable, tone), with history; announcement banner across the portal; migration notify_0003
- [X] T144 [US6] « Since your last visit » from every domain: my requests available, ticket answers and feedback replies, new titles, news, my progress, new shop items, services in trouble (back-to-normal grouped); one line each with an icon and a detail
- [X] T145 [US7] Media page: request journey (requested, approved, released — cinema/digital/physical, searched by Radarr/Sonarr, downloading with the torrent clients' state, imported or waiting for a manual import, available) with an on-demand indexer search (`media.acquisition`); qBittorrent and Deluge connectors (`media.download_clients`); swipeable artwork (TMDB backdrops and posters); books' Grimmory facts (series, publisher, pages, ISBN); sources with a link and an explicit failing-sync label; no duplicate summary
- [X] T146 [US6] Widget option « hide when empty » (`_hide_empty` frame key): an empty widget is collapsed outside editing and the rows close up
- [X] T147 [US7] Title pages: « Watch on Plex / Jellyfin » or « Read on Grimmory » primary button over the artwork (`media.item_links`: Plex universal app link by machine identifier, Jellyfin details, Grimmory book page); services' public URL shown and editable in the services administration
- [X] T148 [US7] My requests: every request opens its title's page (requests linked by kind-aware strong ids; a film or series no library holds yet gets its own, not-available title); list and coming soon show the journey's stage (searching, downloading %, out on…, available) instead of « processing »
- [X] T149 [US7] Covers: a busy or unreachable source postpones the fetch 10 min without spending attempts; two fetches at a time per source; hourly backfill of missing covers spread out in the queue; « no such item » (HTTP 404, `not_found` result) is an answer, never an outage that opens the circuit; a service left unavailable by a restart recovers on its first answer; Grimmory moods and tags as themes, publication date
- [X] T150 [US5] Driven sync (`SyncDriver`, `driven` bindings): watch history (Tautulli, Plex, Grimmory) and TMDB metadata enrichment run from « sync now », the scheduled sync and resyncs with the live progress bar of the services page
- [X] T151 [US7] Title pages: no download manager link (journey, sources link only to the title's own page in a library); the indexers' interactive search is an advanced feature unlocked per member (`media.release_search`, user-grantable, sold as a Marketplace « access » product); swipeable artwork is the header itself (gestures pass through the text), TMDB details refreshed when kept before the alternative artwork (`_v` data version)
- [X] T152 [US2] Horizontal scrollers keep their scrollbar away from their content (`--scroller-gap`)
- [X] T153 [US3] Services' status moves under Support for members (incidents, planned maintenance, overall status, one card per service with its public address and its details in a dialog; nothing to add or configure); Statistics move to Explore
- [X] T154 [US6] « Since your last visit » becomes a widget (starter, hideable); one-cell tiles: a shortcut (portal page or https link, several allowed) and a single value (level, Coins, contribution, achievements, unread, incidents, requests left); one-row widgets render as tiles
- [X] T155 [US1] Header: the assistant button only when an assistant is available; a star in the level badge; incidents in progress with their count; phones get home and search on the left, level, notifications and the menu on the right (no bottom bar in the default themes); the navigation starts with the member — profile, level and progress, Coins, contribution (and, on phones, the personal links and sign out)
- [X] T156 [US3] « A service has been down for N minutes » (`service.outage_lasting` at 5, 10, 15, 30, 60, 120 min, with failed probes) and the automation template « Incident when a service stays down »
- [X] T157 [US5] Edit a configured service (name, address and settings, write-only secrets kept when empty, public address, sync interval) with a test of the edited values
- [X] T158 [US10] Automations become an administration hub (overview, new, run history, templates, approvals): cards with trigger sentence, steps and last run; a WHEN / IF / THEN builder with a field per declared parameter, the event's variables, filters, schedules, limits; a detail page with the flow, a dry run on a sample event and runs as step-by-step timelines; `GET /admin/automations` with trigger, steps and runs, `GET /admin/automations/executions`, catalog with event fields; `incident.create`/`ticket.create` declare their parameters
- [X] T159 [US1] The bell opens a notification panel over the page (sheet; full screen on phones): newest first by day, unread marked, tabs all/unread/alerts, mark all read, open = read + go, archive, preferences and the full center one link away
- [X] T160 [US1] Search in the header: answers while typing (pages, then the first results of each kind with a line of context and the provider's label, an object opened directly, « all results »), recent searches only before typing, keyboard operable, announced; phones open it over the header; Ctrl/⌘ K and « / » focus it, the command palette moves to Ctrl/⌘ Shift K
- [X] T161 [US6] Pinned widgets may let members move and/or resize them (`move`, `resize` in the policy; `movable`/`resizable` on instances); the dashboard's edit mode links administrators to the members' widgets page
- [X] T162 [US7] Media statistics: the activity chart in time spent or in plays (per kind)
- [X] T163 [US1] Health at a glance in the header: all good, degraded (services in trouble) or incident (incidents in progress), opening the status page
- [X] T164 [US3] Services carry an importance (critical, major, minor, internal) and an incident delay (minutes; default by importance 5/10/30/never; 0 never) — an outage lasting longer becomes an incident (one per outage, the importance's severity, the portal's language) and is closed when the service is back (`incident_auto_resolve`); never closing incidents a person opened; migration connectors_0004; edited in « Edit »
- [X] T165 [US3] The status page shows the last 48 hours of each service as micro-bars (one per hour: ok, partial, down, no check); the health indicator's « all good » is green
- [X] T166 [US5] Services administration as cards ordered by importance: connector icon, name, state and importance badges (coloured edge), public address, last sync or live progress; « Sync now » and « Edit » at hand, the rest (disable, sync history, follow-up, disconnect with a confirmation) in a « … » menu
- [X] T167 [US3] A service's health in detail, redesigned: state and for how long, the day in figures (availability, downtime, without checks, last sync), the last 48 hours as micro-bars, the changes as a timeline with their durations, incidents, maintenance, errors and tickets only when there are some; dates in the member's language
- [X] T168 [US3] Alerting rules by importance (`health.alertRules`, « Alert rules » dialog at the top of the services administration): incident and its delay, auto-close, notify after N minutes members and/or administrators (each also by e-mail, category `system.health_email`), counts in the portal's health; each service overrides any field (`alerting`, migration connectors_0005 folding connectors_0004's columns); Health announces the outage by the service's name and its return to the same people (the notifications source with the service id is gone); internal services leave the header and status page summary
- [X] T169 [US1] The header's health indicator is an icon button like the bell (no pill), its count in the same small badge; the achievement notification names the achievement and says what it rewards
- [X] T170 [US6] Widget edit tools drawn alike in one row (settings — always, at least the display options —, remove, grip); display options « hide the title » and « without its box » (frame keys `_hide_title`, `_no_box`, defaultable); the members' dashboard page saves policies and starter together with one button (two buttons let a change be lost) and warns of unsaved changes
- [X] T171 [US6] Layout widgets, sold in the shop: progress bar across and upright (level, today's objectives, quests, achievements), separator (line, dashes, dots, gradient, space, label), clock, sticky note, countdown; « since your last visit » without its inner background
- [X] T172 [US11] New shop looks without duplicates: notification shapes (square tile, bubble, cloud, ticket, label, two-tone), entrance animations (rise, wipe, focus, jelly, shake), accent palettes (polar, copper, solar, berry, slate, peach, crimson — no shared pair, AA tested)
- [X] T173 [US3] Campaigns use the width: identity and boosts beside the time left, « day N of M » progress (page and widget, the running window); shop notices name the product in the owner's language
- [X] T174 [US3] Incident steps in their own colours (investigating red, identified amber, monitoring blue, resolved green) on cards, widget and timeline; the incidents page loads its own styles (its status banner was unstyled when opened directly)
- [X] T175 [US6] Services widget redesigned (a ring of how many work, a chip per troubled state, a tile per service ringed in its state with its 24 h availability, trouble then importance first) and a new compact one-line widget (`health.services_compact`)
- [X] T176 [US6] Widget catalog: searchable, « to add » and « already there » apart, shop widgets no longer mixed in — one line says how many more the shop has, like Appearance
- [X] T177 [US11] Universe notification looks: styles space saga, pirate, manga panel, film noir, VHS; entrance animations film wipe (right to left), iris, and the four elements air, water, earth, fire; sold in the shop
- [X] T178 [US11] New ambient layers (VHS tape, wind, tide, sky lanterns, 8-bit sky), badge styles (VHS, pixel art, terminal, water, wind, light blade) and a new cosmetic type `level_badge` — the level (XP) badge's look (classic free; pixel, neon, crest, gem, hologram, VHS, light blade, four elements sold), chosen in Appearance (`ui.levelBadge`), previewed and tried in the shop
- [X] T179 [US1] Themes Sin City (black and white with red, film-reel navigation, noir notifications wiping in) and Plex (charcoal and amber, sidebar and bottom bar, its words); a new navigation principle « reel » (sections as frames of a film strip); migration ui_0005 seeds both themes
- [X] T180 [US11] Notification animations black hole, melt, KAPOW! and dimensional portal, each with its own exit; every notification now leaves with an animation before it goes (none under reduced motion)
- [X] T181 [US11] The level badge is a profile slot (`level`) everyone sees — header, navigation, profile; « classic » changes rank every ten levels (legend from 100, mythic from 250); new looks black hole, melting, KAPOW!, portal, inferno and an exclusive crown; chosen in Appearance and in the profile customiser
- [X] T182 [US9] Some achievements unlock cosmetics (`unlocks`: badge, title, frame, background, level badge, level-up…) offered once committed through `marketplace.gifts`; reward-only products are out of sale (« unavailable ») and their designs stay exclusive; a new « The Collector » achievement; achievement cards say what they give
- [X] T183 [US9] The level-up moment: the new level and its rank, the XP that did it, the level rewards crossed, the achievements unlocked and what they gave, what the shop now offers at this level (`GET /me/level-ups/{level}`); six looks (classic, arcade, cosmic, comic, four elements, premiere — the last one an achievement's reward), chosen in Appearance (`ui.levelUp`), tried in the shop; packs updated (each universe gets its level badge and looks; level badges, level-ups, elements, retro, comics and cosmos packs) and a « Level badges and level-ups » shelf
- [X] T184 [US11] Every universe celebrates its levels its own way: a level-up per theme (`motion.levelUp`; spell, crawl, decode, sandstorm, blood moon, pumpkin, gift, manga, boing, hearth, HUD, minimal, abduction, hero, synthwave, disco, glitch, noir, spotlight) followed by default (`ui.levelUp` = « theme »), each also sold and in its universe's pack; layouts vary — card, banner, opening crawl, scroll, terminal, comic panels, split screen
- [X] T185 [US1] The Upside Down universe: a theme (red neon, spores, a new « lights » navigation — sections under a string of Christmas lights), notifications cracked with red veins and a faint fading mirror, entering from below and flipping up, banners (Upside Down, Hawkins lights), frames (red veins, lights), a name style with its mirror, ambiences (spores rising, red veins), a Christmas-lights celebration, badge styles (veins, mirror), level badges (Upside Down, veins, lights), its level-up (the world turns over), a palette, badges and titles, an ultimate pack; migration ui_0006
- [X] T186 [US1] The Middle-earth universe: a parchment theme with a map screen, elven and One Ring notifications, Balrog and Eye entrances, banners (the Shire, Mordor, the Shire in pixel art), frames (One Ring, elven), name styles (elvish gold, fires of Mordor), ambiences (meadow, ash), wizard's fireworks, badge styles (ring, elven), level badges (One Ring, the Eye, mithril, Balrog), its level-up (the ring turning, the scroll unrolling), a palette, badges and titles, an ultimate pack; more level badges (frost, nebula, circuit)
- [X] T187 [US1] The Upside Down reworked: red lightning that stays (rifts down the sky like cracks, bolts zigzagging into forks, some trunks thick, joints sometimes rounded; a blurred halo, a red glow, a pale hot core) — generated once as static images (`frontend/scripts/gen-upsidedown.mjs` → `upsidedown.css`) and only flickered in opacity, so nothing is repainted every frame; in the background three faint rifts strike, hold and come back elsewhere on their own rhythms (none, one or several at a time, never crowding the page); it also draws the veins ambience, frame, badge and title styles, level badges, banner and level-up; the notification becomes the show's title sequence (hollow red neon letters closing in between the logo's two growing bars, the message typed like a lab report); detailed particles (torn ash flakes tumbling, dandelion-like spores, embers, big close flakes) without per-particle filters
- [X] T188 [US1] The VHS universe: a theme (blue screen, VT323 font, a new « vcr » navigation — PLAY, the section as a numbered channel, ◀◀ ▶▶ to zap, a tape counter, MENU opening the blue on-screen menu), the VHS notification reworked (tracking band, PLAY ▶) and a bad-tracking entrance leaving like a TV switched off, banner (blue screen), frame (tape rainbow), name style, rewind celebration, level badges (VHS reworked, cassette), its level-up (the TV comes on, PLAY ▶ blinking), a palette, badges and titles, a VHS pack and an ultimate pack; migration ui_0007
- [X] T189 [US1] The Nova universe (ultra-modern): a new « sheet » navigation — a phone's bottom bar with a round button in the middle raising a sheet of app icons (a section with several pages opens as a folder, Back returns; Escape, the backdrop or dragging the handle closes it), island notifications (a black capsule at the top) and a morph entrance, colour mesh banner, activity rings frame, gradient name, bloom celebration, bokeh ambience, glass badge style, app-icon level badge, its level-up (a frosted sheet sliding up), a palette, badges and titles, a Nova pack and an ultimate pack
- [X] T190 [US9] The shop shows every level-up look as itself: the real moment in miniature (its stage, card and particles) instead of one generic picture
- [X] T191 [US11] A universe theme alone brings its colours, fonts, layout, navigation and words; its sold looks (animated background, notification style and entrance, celebration, level-up) are worn only by their owners — « follow the theme » falls back to the free defaults otherwise (`resolveLooks` with the member's locked looks, Appearance says the theme's own look is in its pack); every ultimate pack holds the sold looks its theme uses (built from the theme, checked by a test) and the theme's description says so
- [X] T192 [US8] The shop, clearer: a « theme » product is now an **interface** (the portal's look only) and an ultimate pack a **theme pack** (the interface and all its looks); departments Themes (theme packs, interfaces, palettes), Profile (banners, avatar frames, profile backgrounds, name styles, badges, titles, level badges), Notifications & effects (notification styles, notification animations, ambiences, celebrations, level-ups), Features and Packs, one shelf per kind; a product's page lists the packs it is part of (one item among the pack's, with a link), and a pack's items link to their own page

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (1)** → **Foundational (2)** → user stories.
- **US1 (header)** and **US2 (sections)** depend only on Phase 2; US1's `PersonalMenu` receives `personal`
  entries once US2 T037–T038 land (until then it shows profile/progression/sign-out).
- **US3 (frames)** depends on US2 (`SectionNav`) and US1 (`AppHeader`).
- **US4 (pages)** depends on Phase 2 kit; can run in parallel with US1–US3 per folder.
- **US5 (themes)** depends on US3 (frames) and US4 (kit adopted) to honor every variant.
- **US6 (dashboard)** depends on Phase 2 (+ T003 fixtures); independent of US1–US5 otherwise.
- **US7** depends on Phase 2; T082 needs T036 (welcome setting).
- **Polish** last.

### Within Each Story

Tests first (fail), then backend model/service/API, then OpenAPI/client regeneration, then UI, then e2e.

### Parallel Opportunities

- Phase 2: T005, T008, T013–T018 in parallel after T004.
- US1: T021, T022, T024, T025 in parallel.
- US2: T030, T031 in parallel; backend T032–T036 before T037.
- US4: T049–T057 fully parallel (different feature folders).
- US6: T065–T068 in parallel; T069 and T070 in parallel.

## Parallel Example: User Story 4

```text
T050 media pages · T051 content pages · T052 services/statistics · T053 support
T054 community/gamification · T055 marketplace · T056 personal pages · T057 administration
```

## Implementation Strategy

### MVP First

1. Phases 1–2 (theme v2, tokens, kit).
2. US1 header → US2 sections → US3 frames: the reported problems (raw look, flat menu, no header, phone
   column defect) are fixed. **Stop and validate** on the LAN deployment.

### Incremental Delivery

3. US4 page migration (folder by folder, each shippable).
4. US6 dashboard editor (independent backend + frontend slice with migration).
5. US5 layout-capable themes (all variants honored, validation).
6. US7 sign-in & welcome, then Polish.

### Notes

- One commit for the whole spec when complete (implementation workflow), tasks marked `[X]` as they finish.
- Keep `groups` and `PUT /dashboard/layout` aliases until the next release (XIX).
