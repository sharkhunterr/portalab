# Feature Specification: Visual Experience (Default Theme, Header, Grouped Navigation, Layout-Capable Themes)

**Feature Branch**: `027-visual-experience`
**Created**: 2026-10-04
**Status**: Draft
**Input**: User description: "on va complètement retravailler l'aspect visuel! Cela doit vraiment être convivial, simple et moderne. Cela doit être compatible smartphone, desktop, tablette. Ne pas oublier que c'est le thème par défaut mais qu'il y aura plein d'autres thèmes (pas juste la couleur/font... qui change mais bien disposition, animation, sons,...). Dans le menu il y a plein de sous-menus qui doivent regrouper (support, communauté, media,...). Il faut penser à avoir un header avec image user, niveau, coins, menu, searchbar,... Normalement cela était décrit dans les docs, vérifie si besoin"

## Role of This Document

This is a **detailed feature specification** for the portal's **visual experience**: the default look and
feel, the personal header, the grouped navigation, the responsive layouts for phone/tablet/desktop, and
the ability of themes to change **layout, motion and sound** — not only colors and fonts. It refines and
completes the Portal Core shell (`specs/004-portal-core-shell/spec.md`) and Personalization, Themes &
Accessibility (`specs/022-personalization-themes-a11y/spec.md`), consumes Identity (`002`, avatar and display
name), Gamification & Economy (`013`, level, XP, Coins), Notifications (`010`), Search & Command Palette
(`008`), the Dashboard (`009`) and Extensibility (`023`, plugin themes and navigation contributions), under
the project Constitution (`.specify/memory/constitution.md`). It draws on `ux/UX_PRINCIPLES.md`,
`ux/DESIGN_SYSTEM.md`, `ux/THEMING.md` and `product/PRODUCT_BLUEPRINT.md` (module list: Home, Media,
Community, Statistics, Support, Marketplace, Services, News, Calendar, Administration).

**Why this spec exists**: the 26 implemented specs fixed behavior, permissions and accessibility, but no
document described the visual composition of the portal (header content, menu grouping, page
composition, visual identity). The result is functional but raw: a flat menu of ~50 entries, a header with
no personal status, unstyled stacked cards, and a mobile layout defect. This spec defines what a
friendly, simple and modern experience means for the portal, as a **default theme** among many.

Scope boundary: this spec **owns** the default visual identity, the header composition, navigation
sections and their presentation, responsive layout behavior per device class, the page composition
patterns shared by all modules (page header, cards, lists, empty/loading states), the **layout and
motion/sound profiles** a theme may select, and celebratory feedback for progression. It does **not**
change functional logic, permissions, business rules, the set or meaning of functional states, or what
data a user may see — by definition (022 FR-001..003, 004 FR-031). It chooses no technology and contains no
implementation detail.

### Experience Principles (normative)

- **Friendly, simple, modern**: generous spacing, clear hierarchy (one primary action per area), rounded
  surfaces, readable typography, meaningful icons next to labels, subtle motion, illustrated empty states.
- **One environment**: every page sits in the same frame (header, navigation, page header, content) on
  every device; modules and plugins inherit it without designing their own chrome.
- **Personal at a glance**: the user always sees who they are, where they stand (level, Coins) and what
  needs their attention (notifications), without opening a page.
- **Grouped, not flat**: navigation is organized in a small number of understandable sections; nothing is
  hidden that the user may use, but nothing is shown that they cannot use.
- **Themes are experiences**: a theme may change arrangement, motion, sounds and atmosphere — always within
  the presentation boundary and the accessibility floor.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A personal header on every page (Priority: P1)

On every authenticated page, the user sees a header showing their avatar (or initials), their current level
with progress toward the next one, their Coins balance, a notification bell with an unread count, a search
bar (or search button on small screens), the assistant entry and a menu control. Activating the avatar opens
a personal menu (profile, progression, my account, appearance, language, sign out).

**Why this priority**: the user explicitly expects the header to carry identity, level, Coins, menu and
search; it is the first thing seen on every page and the main signal that the portal is "theirs".

**Independent Test**: Sign in as a user with an avatar, level 3 and 120 Coins; on any page confirm the header
shows the avatar, "Level 3" with progress, "120" Coins, the unread count, the search entry and the menu
control; open the personal menu and reach each destination; repeat on phone, tablet and desktop widths.

**Acceptance Scenarios**:

1. **Given** a signed-in user with an avatar, **When** any page is displayed, **Then** the header shows the
   avatar, level with progress toward the next level, Coins balance, notifications with unread count, search
   and the menu control.
2. **Given** a user without an avatar, **When** the header renders, **Then** a generated placeholder (initials
   on a stable color) is shown instead of an empty image.
3. **Given** the user earns XP or Coins, **When** the change is known to the portal, **Then** the header values
   update without a page reload and the change is acknowledged by a short, non-blocking animation (and a
   sound if sounds are enabled).
4. **Given** the user reaches a new level, **When** the header updates, **Then** a celebratory feedback is
   shown once (respecting reduced motion and sound-off), and it never blocks interaction.
5. **Given** gamification is disabled or the progression data is unavailable, **When** the header renders,
   **Then** the level/Coins area is omitted or shows a neutral unavailable state, and the rest of the header
   works normally.
6. **Given** a phone-width screen, **When** the header renders, **Then** it stays on a single compact row
   (avatar, level badge, Coins, notifications, search button, menu) without wrapping or horizontal scrolling.
7. **Given** the user activates the avatar, **When** the personal menu opens, **Then** it offers profile,
   progression, account, appearance, language and sign out, and is fully operable by keyboard and touch.

---

### User Story 2 - Navigation grouped in clear sections (Priority: P1)

Instead of one flat list, navigation is organized into a small set of named sections, each with an icon,
that expand to show their pages — for example: Home; Media (library, requests, linked accounts); Content
(news, wiki, calendar); Services (status, statistics); Support (incidents, tickets, feedback); Community
(members, leaderboards, quests, projects, progression); Marketplace (catalog, community projects); and, for
administrators only, an Administration area. Personal pages (account, appearance, language, notification
preferences, privacy) live in the personal menu, not in the main navigation.

**Why this priority**: the current flat menu (~50 entries for an administrator) is the main source of
confusion the user reported; grouping is required for the portal to feel simple.

**Independent Test**: Sign in as an administrator and as a regular user; confirm the main navigation shows at
most 9 top-level sections, that each section expands to its pages, that a section the user cannot use is
absent, and that every previously reachable destination is still reachable.

**Acceptance Scenarios**:

1. **Given** the default configuration, **When** a regular user opens the navigation, **Then** they see named
   sections with icons (not a flat list), at most 9 at the top level, each expanding to its pages.
2. **Given** a section containing a single permitted page, **When** navigation renders, **Then** the section
   behaves as a direct link (no one-item sub-menu).
3. **Given** a section with no page the user may use, **When** navigation renders, **Then** the section is
   absent (no empty sections, no hint of hidden pages).
4. **Given** the user is on a page, **When** navigation renders, **Then** that page and its section are marked
   as current and the section is expanded.
5. **Given** an administrator, **When** they open navigation, **Then** administration pages appear under one
   Administration area grouped by topic (users & access, services & integrations, content & community,
   economy & marketplace, system & monitoring, extensions), not mixed into user sections.
6. **Given** a module or plugin contributes a page, **When** navigation renders, **Then** the page appears in
   the section it declares (or a default section for its owner), and a page declaring an unknown section is
   placed in a fallback section rather than lost.
7. **Given** an administrator reorganizes sections (order, membership, names) within policy, **When** users
   open navigation, **Then** the new organization applies without changing anyone's permissions.
8. **Given** the user expands or collapses sections, **When** they come back later or on another device,
   **Then** their expansion choices are remembered.

---

### User Story 3 - Comfortable on phone, tablet and desktop (Priority: P1)

The portal adapts its arrangement to the device: on phones, a compact header, a bottom bar for the most
important destinations (home, search, notifications, menu) and a full-height menu panel for the sections; on
tablets, a collapsible side rail with icons; on desktops, a full side navigation with labels and a wide search
bar. Content reflows into one, two or more columns according to the available width.

**Why this priority**: the user requires smartphone, tablet and desktop compatibility; today's phone layout
wastes a full column on a misplaced menu button.

**Independent Test**: Open the home page, a list page, a detail page and a form at phone, tablet and desktop
widths, in portrait and landscape; confirm no horizontal scrolling, no wasted column, every navigation
destination reachable, and touch targets comfortable on touch devices.

**Acceptance Scenarios**:

1. **Given** a phone-width screen, **When** any page renders, **Then** the content uses the full width, the main
   destinations are in a bottom bar, and the section menu opens as a panel from a menu control.
2. **Given** a tablet-width screen, **When** any page renders, **Then** navigation is a collapsible rail of
   section icons with labels available on expansion, and content uses the remaining width.
3. **Given** a desktop-width screen, **When** any page renders, **Then** navigation shows sections with labels,
   the search bar is wide and always visible, and content is laid out in a centered, readable width.
4. **Given** the device is rotated or the window resized, **When** the width class changes, **Then** the layout
   switches without losing the current page, scroll position, open dialogs or entered text.
5. **Given** a touch device, **When** the user interacts, **Then** interactive targets are comfortably sized for
   touch and no action requires hover.

---

### User Story 4 - A modern, consistent page composition (Priority: P2)

Every page follows the same composition: a page header (title, short description or context, primary action,
secondary actions), then content made of consistent building blocks — cards with clear titles, lists with
avatars/icons and meta information, tiles for collections (media, products, projects), status chips with
icon and text, and illustrated empty states with a next action. The home dashboard arranges its widgets in a
responsive grid with a friendly greeting and a "since your last visit" summary.

**Why this priority**: consistency is what makes the portal feel simple and modern across 20+ modules; it
follows the header and navigation, which frame every page.

**Independent Test**: Visit one page of every module; confirm each shows the standard page header, uses the
shared building blocks, presents loading as skeletons shaped like the content, and presents empty states with
an illustration, a short explanation and a next action.

**Acceptance Scenarios**:

1. **Given** any module page, **When** it renders, **Then** it shows a page header with title, optional context
   line, and its primary action placed consistently.
2. **Given** data is loading, **When** the page renders, **Then** skeleton placeholders shaped like the expected
   content appear instead of blank areas or bare spinners, and independent areas load independently.
3. **Given** a list or collection has no items, **When** it renders, **Then** an illustrated empty state explains
   why and offers a relevant next action (never a dead end).
4. **Given** the home page, **When** it renders, **Then** it greets the user by name, shows a "since your last
   visit" summary, and arranges widgets in a responsive grid (one column on phones, more on larger screens).
5. **Given** any functional state (loading, partial, stale, error, unavailable, maintenance, unauthorized, no
   data, syncing), **When** it is displayed, **Then** it uses the standard state presentation of the active
   theme (icon + text + color), identical in meaning across modules.

---

### User Story 5 - Themes that change arrangement, motion and sounds (Priority: P2)

The friendly modern look is the **default theme**. Other themes — built-in, from administrators, from the
Marketplace or from plugins — can change not only colors and fonts but also the **arrangement** (navigation
placement and style, header arrangement, card style, density, content width), the **motion** (transition
style, animation intensity, celebratory effects) and the **sounds** (notification, reward and level-up
sounds). The user switches theme and the whole experience changes instantly, while meaning, data, permissions
and accessibility stay the same.

**Why this priority**: the user insists themes must go beyond colors; designing the default theme as one
instance of a layout-capable theme model prevents hard-coding the default look into every page.

**Independent Test**: Switch between the default theme and two contrasting themes (e.g., one with top
navigation and flat cards, one with a side rail, playful motion and a different sound set); confirm the
arrangement, motion and sounds change, while every destination, every functional state's meaning and every
datum stay identical, and accessibility preferences still override.

**Acceptance Scenarios**:

1. **Given** the default theme, **When** the user selects another theme with a different layout profile,
   **Then** navigation placement, header arrangement and card style change immediately without reloading and
   without losing the current page or entered data.
2. **Given** a theme with a different motion profile, **When** the user navigates or earns a reward, **Then**
   transitions and celebratory effects follow that profile; **and given** reduced motion is enabled, **Then**
   motion is suppressed or minimized whatever the theme.
3. **Given** a theme with its own sound set, **When** a notification or reward occurs, **Then** the theme's sound
   is used; **and given** sounds are off, **Then** no sound plays whatever the theme.
4. **Given** a theme declares an arrangement option the portal does not offer, **When** it is submitted,
   **Then** it is refused with an explanation (themes choose among supported arrangements; they never inject
   code or arbitrary structure).
5. **Given** any theme, **When** it is active, **Then** every navigation destination, header element and
   functional state remains present and reachable — a theme may move or restyle them, never remove critical
   ones (search, notifications, menu, identity, sign out).
6. **Given** a light/dark system preference, **When** the default theme is active, **Then** it follows the
   device preference unless the user chose otherwise.
7. **Given** the administrator restricts available themes or forces a default, **When** users choose
   appearance, **Then** only allowed themes are offered (existing 022 policy).

---

### User Story 6 - Welcoming sign-in and first visit (Priority: P3)

Screens shown before or right after sign-in (sign-in, registration, password reset, first-run setup, the very
first home visit) share the same visual identity: a branded, centered, friendly layout, clear errors, and a
short first-visit welcome that points to the main sections, the header elements and appearance settings.

**Why this priority**: first impressions matter but these screens are visited rarely compared with the shell.

**Independent Test**: Sign out, open the sign-in page on phone and desktop, sign in as a new user and confirm
the welcome appears once, can be dismissed, and is not shown again.

**Acceptance Scenarios**:

1. **Given** an anonymous visitor, **When** the sign-in page renders, **Then** it uses the portal identity
   (name, logo or mark, default theme) in a centered card that is comfortable on phone and desktop.
2. **Given** a user's first visit, **When** the home page renders, **Then** a dismissible welcome introduces the
   header, sections and appearance settings; once dismissed it does not reappear on any device.

### Edge Cases

- **Very long names or large numbers**: long display names are truncated with the full name available on
  focus/hover/long-press; large Coins balances use compact notation (e.g., 12.4k) with the exact value
  available.
- **Avatar fails to load**: the initials placeholder is shown; no broken image.
- **Header data partially unavailable** (progression service down, notification count failing): each header
  element degrades independently; search, menu and sign out always remain available.
- **Many plugin pages in one section**: a section with many pages stays scannable (sub-grouping or
  "show more"), never pushing other sections off-screen without scrolling the navigation itself.
- **Plugin or module disabled while the user is on its page**: its navigation entry and section disappear on
  next evaluation; the current page shows the standard unavailable state (004 FR-028).
- **Theme switched mid-interaction** (dialog open, form half-filled): state and entered data are preserved.
- **Theme with a layout profile unsuitable for phones**: on phones, the portal falls back to the theme's phone
  arrangement or the default phone arrangement, so the experience stays functionally complete.
- **Right-to-left languages**: navigation, header and bottom bar mirror correctly.
- **200 % text size / high contrast / reduced motion**: the header and navigation stay usable without
  overlap; motion and celebratory effects are minimized; contrast floor holds.
- **Offline or slow connection**: the frame (header, navigation, page header) renders first with skeletons; a
  slow area never blocks the rest.
- **Rapid successive rewards**: celebratory feedback is coalesced (no stack of animations or sounds).

## Requirements *(mandatory)*

### Functional Requirements

#### Header
- **FR-001**: Every authenticated page MUST show a header containing: the user's avatar (or generated initials
  placeholder) and display name (name may be hidden on small screens), current level with progress toward the
  next level, Coins balance, notifications entry with unread count, search entry, assistant entry, and a menu
  control.
- **FR-002**: The header MUST show only the signed-in user's own data, and only data that user is allowed to
  see; it MUST NOT expose other users' data.
- **FR-003**: Activating the avatar MUST open a personal menu offering at least: profile, progression, account,
  appearance, language, notification preferences, privacy, and sign out.
- **FR-004**: Header values (level, progress, Coins, unread count) MUST refresh without a page reload when the
  underlying values change, within the portal's normal live-update delay.
- **FR-005**: Each header element MUST load and fail independently; an unavailable element MUST show a neutral
  state and MUST NOT hide search, menu, notifications or sign out.
- **FR-006**: When gamification is disabled for the portal or the user, the level and Coins elements MUST be
  omitted without leaving empty space.
- **FR-007**: XP and Coins gains MUST be acknowledged by a short, non-blocking feedback; reaching a new level
  MUST be celebrated once; feedback MUST respect reduced motion and sound preferences and be coalesced when
  several gains arrive together.

#### Navigation sections
- **FR-008**: Main navigation MUST be organized into named sections with icons; by default at most 9
  top-level sections are shown to any user.
- **FR-009**: The portal MUST provide a default section set covering the product modules: Home, Media,
  Content (news, wiki, calendar), Services (status, statistics), Support, Community (including progression,
  leaderboards, quests), Marketplace (including community projects), and Administration (administrators only).
- **FR-010**: Every navigation contribution (module or plugin) MUST be able to declare the section it belongs
  to; contributions without a valid section MUST land in a default section for their owner or a fallback
  section, and MUST never be dropped.
- **FR-011**: Sections MUST be filtered like entries: a section with no permitted entry MUST be absent; a
  section with one permitted entry MAY be rendered as a direct link.
- **FR-012**: Personal destinations (account, appearance, language, notification preferences, privacy, linked
  media accounts) MUST be reachable from the personal menu and MUST NOT clutter the main sections.
- **FR-013**: Administration destinations MUST be grouped under a single Administration area, organized by
  topic, and MUST be shown only to users holding at least one administration permission.
- **FR-014**: The current page and its section MUST be indicated, and the section MUST be expanded on arrival.
- **FR-015**: Users' section expansion choices MUST persist across sessions and devices.
- **FR-016**: Administrators MUST be able to rename, reorder and re-assign entries between sections within
  policy; such changes MUST never alter permissions (existing 004 admin layout extended to sections).
- **FR-017**: Breadcrumbs MUST reflect the section → page hierarchy.

#### Responsive layouts
- **FR-018**: The portal MUST provide distinct arrangements for three device classes — phone, tablet, desktop —
  each functionally complete (004 FR-022/023).
- **FR-019**: On phones, the most important destinations (home, search, notifications, menu) MUST be reachable
  with one tap from a persistent bar, and the full section menu MUST open as a panel; no layout element MAY
  occupy a permanent empty column.
- **FR-020**: No page MAY require horizontal scrolling at any supported width (from 320 px wide), except
  inside explicitly scrollable content such as wide tables.
- **FR-021**: Switching device class (rotation, resize) MUST preserve the current page, scroll position, open
  dialogs and entered data.
- **FR-022**: On touch devices, no action MAY depend on hover, and interactive targets MUST be comfortably
  sized for touch.

#### Page composition & building blocks
- **FR-023**: Every page MUST use a standard page header (title, optional context line, primary action,
  secondary actions) provided by the shared design system.
- **FR-024**: The design system MUST provide the building blocks pages are composed of — cards, lists with
  leading avatar/icon and metadata, tiles for collections (media, products, projects, achievements), status
  chips, progress bars, statistics figures, tabs, dialogs and panels — and every module page MUST use them
  instead of ad-hoc presentation.
- **FR-025**: Loading MUST be presented with skeletons shaped like the expected content; independent areas MUST
  load independently.
- **FR-026**: Empty states MUST include an illustration or icon, a short explanation and a relevant next action.
- **FR-027**: The home page MUST greet the user by name, show the "since your last visit" summary, and arrange
  widgets in a responsive grid.
- **FR-028**: Pages shown before sign-in (sign-in, registration, recovery, first run) MUST use the portal's
  visual identity and be comfortable on phones and desktops.
- **FR-029**: A first-visit welcome MUST introduce the header, sections and appearance settings, be dismissible,
  and not reappear once dismissed.

#### Default theme & layout-capable themes
- **FR-030**: The portal MUST ship a new default theme embodying the experience principles (friendly, simple,
  modern), with light and dark variants that follow the device preference unless the user chose otherwise;
  existing built-in themes (including high contrast) MUST remain available.
- **FR-031**: A theme MUST be able to select, in addition to the 022 capabilities (colors, typography, icons,
  backgrounds, textures, borders, shadows, density, animations, transitions, notification presentation,
  sounds): a **layout profile** (navigation placement and style per device class, header arrangement, card
  style, content width, corner and elevation style), a **motion profile** (transition style, animation
  intensity, celebratory effects) and a **sound set** (notification, reward, level-up and interface sounds).
- **FR-032**: Layout profiles MUST be chosen among arrangements the portal supports; a theme MUST NOT define
  arbitrary structure or executable content, and an unsupported option MUST be refused with an explanation.
- **FR-033**: No theme MAY remove or make unreachable a critical element: search, notifications, menu/
  navigation, personal menu, sign out, functional states, and any navigation destination the user may use.
- **FR-034**: Switching themes MUST apply immediately, without reload, preserving the current page, scroll
  position, dialogs and entered data.
- **FR-035**: Accessibility preferences (reduced motion, contrast, text size, sound off) MUST override any theme
  layout, motion or sound profile, and every theme MUST pass the accessibility floor (022 FR-011..014) with its
  layout profile applied on all device classes.
- **FR-036**: Themes from administrators, the Marketplace and plugins MUST be able to use layout, motion and sound
  profiles under the same validation, policy and enablement rules as existing themes (022, 023).
- **FR-037**: Modules and plugins MUST obtain the header, navigation, page header and building blocks from the
  shell and design system, so that a theme change restyles them without per-module work.

### Key Entities *(include if feature involves data)*

- **Navigation Section**: a named, iconified group of navigation entries (key, label, icon, order, audience such as
  "everyone" or "administration", optional topic sub-groups); its visibility derives from the entries the user
  may use.
- **Navigation Entry (extended)**: the existing contribution (004) gains the section it belongs to.
- **Personal Header Summary**: the signed-in user's own display name, avatar, level, progress toward next level,
  Coins balance and unread notification count, each with its own availability state.
- **Layout Profile**: a theme's choice among supported arrangements — navigation placement/style per device class,
  header arrangement, card style, content width, corner and elevation style.
- **Motion Profile**: a theme's transition style, animation intensity and celebratory effect style.
- **Sound Set**: a theme's sounds for notifications, rewards, level-up and interface events.
- **Theme (extended)**: the existing 022 theme definition plus optional layout profile, motion profile and sound
  set; the default theme provides all three.
- **Navigation Preferences**: per-user expanded/collapsed sections and dismissed first-visit welcome, persisted at
  account level.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On 100% of authenticated pages and on all three device classes, the header shows identity, level,
  Coins (when gamification is enabled), notifications, search and menu.
- **SC-002**: An administrator sees at most 9 top-level navigation sections (down from ~50 flat entries today); a
  regular user sees at most 8.
- **SC-003**: Every destination reachable before the redesign remains reachable, in at most 2 interactions from
  the navigation on desktop and at most 3 on phones.
- **SC-004**: 0 pages require horizontal scrolling at widths from 320 px to 2560 px (outside explicitly
  scrollable content).
- **SC-005**: In a hallway test, at least 9 of 10 participants find a given page (e.g., "open a support ticket",
  "see the leaderboard", "check my Coins") within 10 seconds on first attempt.
- **SC-006**: Switching between three themes with different layout profiles changes the arrangement in under 1
  second without reload, with 0 lost inputs and 0 missing critical elements.
- **SC-007**: 100% of module pages use the standard page header and design-system building blocks (no ad-hoc
  page chrome remains).
- **SC-008**: 100% of empty states provide a next action; 100% of loading areas show content-shaped skeletons.
- **SC-009**: Accessibility conformance (WCAG 2.2 AA) is maintained for every built-in theme on every device
  class; reduced motion and sound-off are honored in 100% of celebratory feedback.
- **SC-010**: A reward or level change is reflected in the header within the portal's normal live-update delay
  (a few seconds) in 95% of cases, without page reload.

## Assumptions

- **Visual direction** (no reference was provided): the default theme takes the "friendly modern app" direction
  — rounded cards with soft elevation, generous whitespace, one vivid accent color, readable sans-serif type,
  line icons next to labels, light illustrations for empty states, subtle micro-animations; it can be refined in
  `/speckit.clarify` without changing the requirements.
- **Device classes**: phone < 640 px, tablet 640–1024 px, desktop > 1024 px wide (indicative; exact breakpoints
  are a planning detail).
- **Default sections** follow the product module list (PRODUCT_BLUEPRINT); exact labels and the membership of
  each existing entry are a planning detail, adjustable later by administrators.
- **Header data** reuses existing capabilities: identity (display name, avatar — 002), progression (level, XP,
  Coins — 013), notification summary (010), search and palette (008), assistant (018); no new business data is
  created.
- **Themes stay declarative**: layout/motion/sound profiles extend the existing inert theme document (022) with
  choices among supported options; no theme carries code.
- **Sounds are off by default** for new users (existing 022 preference), so the default theme's sound set is
  only heard when the user enables sounds.
- **The existing light, dark and high-contrast themes** become variants of or companions to the new default
  theme; existing user theme preferences keep working (a stored choice that no longer exists falls back to the
  default theme).
- **Scope**: all existing module pages are re-composed with the shared building blocks; no business feature is
  added, removed or changed.
