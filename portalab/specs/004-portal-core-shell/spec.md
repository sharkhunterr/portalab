# Feature Specification: Portal Core — Global Shell & Navigation

**Feature Branch**: `004-portal-core-shell`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Detailed functional specification of the Portal Core (global shell & navigation)."

## Role of This Document

This is a **detailed feature specification** for the Portal Core shell and navigation — the
permanent frame that hosts every module, plugin, and page and makes the portal feel like one
coherent environment. It conforms to and refines the superior reference specification
(`specs/001-portal-global-spec/spec.md`), and composes with Identity & Users
(`specs/002-identity-users/spec.md`) and Roles & Permissions
(`specs/003-roles-permissions/spec.md`), under the project Constitution
(`.specify/memory/constitution.md`, v1.0.0). It draws on `architecture/FUNCTIONAL_ARCHITECTURE.md`,
`ux/UX_PRINCIPLES.md`, and `ux/DESIGN_SYSTEM.md`.

Scope boundary: this spec owns the **shell** (persistent frame, navigation, dynamic navigation
assembly, breadcrumbs, contextual navigation, responsive/mobile navigation, the always-reachable
search and AI entry points, the Command Palette, keyboard shortcuts, and the global
loading/error/degraded/unauthorized states). It does **not** own the internal content of specific
modules (Home dashboard, Media, etc.), the search/AI engines themselves, or the authorization
engine — it consumes them. It chooses no technology and contains no implementation detail.

**Terminology** (aligned with the global spec, OQ-1): Domain Event = a recorded fact; Campaign =
a themed time-bound operation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One coherent environment with a persistent shell (Priority: P1)

Wherever a user is in the portal, a single persistent shell surrounds the content: the same
navigation, the same always-reachable search and AI, the same identity/notification surface — so
the portal feels like one environment, not a collection of links to external apps.

**Why this priority**: The "one environment, not a collection of links" principle is the product's
defining promise; the shell is what delivers it on every page.

**Independent Test**: Navigate across several modules and a plugin page; confirm the persistent
shell (navigation, search, AI, identity, notifications) remains present and consistent, and that no
destination feels like leaving the portal for a separate app.

**Acceptance Scenarios**:

1. **Given** any page within the portal, **When** it is displayed, **Then** the persistent shell
   (primary navigation, global search entry, AI entry, identity and notification surface) is present
   and consistent.
2. **Given** a user moves from one module to another, **When** the new page loads, **Then** the
   shell persists without a full reset of context and the user stays oriented.
3. **Given** a module surfaces data from an external service, **When** it is shown, **Then** it is
   presented as an integrated part of the portal, not as a raw link out to a separate application.

### User Story 2 - Navigation evolves automatically with modules, plugins, and rights (Priority: P1)

The navigation is assembled dynamically from the modules and plugins currently available and the
current user's effective permissions, so enabling/disabling a module or plugin, or changing a
user's rights, changes what appears in navigation without manual reconfiguration.

**Why this priority**: Dynamic, rights-aware navigation is explicitly required; it is what keeps the
extensible portal coherent as it grows and what prevents users from seeing areas they cannot use.

**Independent Test**: Enable a module and confirm it appears in navigation for permitted users;
disable it and confirm it disappears; grant/revoke a permission and confirm the corresponding
navigation entry appears/disappears for that user — all without editing a static menu.

**Acceptance Scenarios**:

1. **Given** a module is enabled and the user is permitted, **When** navigation is rendered, **Then**
   the module's entry appears automatically.
2. **Given** a module or plugin is disabled, **When** navigation is rendered, **Then** its entries
   no longer appear and its routes are not reachable.
3. **Given** a user lacks permission for an area, **When** navigation is rendered, **Then** the
   area's entry is not offered to them, and direct navigation to it yields an unauthorized state.
4. **Given** a plugin that adds a page or enriches a module, **When** it is enabled, **Then** its
   navigation contributions integrate into the existing structure rather than creating a parallel
   menu.

### User Story 3 - Orientation: breadcrumbs and contextual navigation (Priority: P2)

On every important page the user can tell where they are, what they can do, what is happening, and
what the relevant next action is — supported by breadcrumbs and context-specific navigation.

**Why this priority**: The UX principle "every page answers where am I / what can I do / what next"
and "no dead-ends" depend on consistent orientation aids.

**Independent Test**: Open a deep page (e.g., a service detail) and confirm breadcrumbs reflect the
path, contextual navigation offers relevant related actions/objects, and there is always a
meaningful next step (no dead-end).

**Acceptance Scenarios**:

1. **Given** a nested page, **When** it is displayed, **Then** breadcrumbs reflect the hierarchical
   path and each ancestor is navigable.
2. **Given** a detail page for an object, **When** it is displayed, **Then** contextual navigation
   surfaces related objects/actions the user is permitted to use.
3. **Given** an otherwise empty or terminal view, **When** it is displayed, **Then** it still offers
   a relevant next action rather than a dead-end.

### User Story 4 - Global search and AI reachable everywhere (Priority: P1)

From anywhere in the shell the user can open global search and the AI; classic search returns
immediately while AI works in parallel, and neither blocks the other nor the rest of the portal.

**Why this priority**: "Search is always easy to reach" and "AI never blocks classic search" are
locked UX principles and product decisions; the shell is responsible for the entry points and their
non-blocking behavior.

**Independent Test**: From several different pages, open global search and the AI via the shell;
confirm classic results appear without waiting for AI, that AI is reachable in parallel, and that an
AI outage leaves search and navigation fully usable.

**Acceptance Scenarios**:

1. **Given** any page, **When** the user invokes global search, **Then** the search entry is
   reachable from the shell and classic results are presented without waiting for AI.
2. **Given** any page, **When** the user invokes the AI, **Then** the AI entry is reachable from the
   shell and runs in parallel without blocking classic search or navigation.
3. **Given** the AI is unavailable, **When** the user searches or navigates, **Then** search and the
   rest of the shell remain fully usable.

### User Story 5 - Command Palette and keyboard shortcuts (Priority: P2)

A Command Palette provides fast keyboard-driven navigation and actions across the portal, offering
only destinations and actions the user is permitted to use; keyboard shortcuts accelerate common
operations.

**Why this priority**: The Command Palette is a named Core capability and a major accelerator for
the "one environment" feel; it must respect permissions like all navigation.

**Independent Test**: Open the Command Palette via keyboard from different pages; confirm it lists
permitted navigation targets and actions, excludes unpermitted ones, and that documented keyboard
shortcuts perform their actions.

**Acceptance Scenarios**:

1. **Given** any page, **When** the user opens the Command Palette (via its shortcut), **Then** it
   offers navigation targets and actions scoped to the user's effective permissions.
2. **Given** an action the user is not permitted to perform, **When** the palette is shown, **Then**
   that action is not offered, and if reached anyway it is refused server-side.
3. **Given** a documented keyboard shortcut, **When** the user triggers it, **Then** the associated
   navigation/action occurs, consistently across the portal.

### User Story 6 - Responsive and mobile-complete navigation (Priority: P2)

The shell adapts to screen size and remains functionally complete on mobile, exposing navigation,
search, AI, and the Command Palette through mobile-appropriate patterns.

**Why this priority**: "Mobile remains functionally complete" and "accessibility is transversal" are
locked UX principles; a reduced mobile shell would break them.

**Independent Test**: Use the portal at phone, tablet, and desktop sizes; confirm navigation,
search, AI, and the Command Palette are reachable and functionally complete at each, with no
critical capability dropped on mobile.

**Acceptance Scenarios**:

1. **Given** a small screen, **When** the shell is displayed, **Then** navigation, search, AI, and
   the Command Palette remain reachable through mobile-appropriate patterns.
2. **Given** any screen size, **When** the user performs a core navigation task, **Then** it is
   completable without requiring a larger screen.
3. **Given** accessibility preferences (keyboard-only, reduced motion), **When** navigating the
   shell, **Then** all shell functions remain operable and preferences take precedence over visual
   effects.

### User Story 7 - Global states: loading, error, degraded, unauthorized (Priority: P1)

The shell renders and keeps the portal usable regardless of partial failures: slow or failing areas
show the correct functional state (loading, error, unavailable, maintenance, unauthorized, etc.)
without blocking unrelated navigation or content.

**Why this priority**: Graceful degradation and "slow components never block unrelated content" are
locked principles; the shell must isolate failures and communicate state clearly.

**Independent Test**: Simulate a slow area, a failing area, an unavailable backing service, and an
unauthorized area; confirm the shell stays usable, each area shows its distinguishable state, and
unrelated navigation/content is unaffected.

**Acceptance Scenarios**:

1. **Given** a slow-loading area, **When** the page renders, **Then** the shell and unrelated content
   remain usable while the slow area shows a loading state.
2. **Given** an area whose backing service is unavailable or in maintenance, **When** displayed,
   **Then** it shows the corresponding distinguishable state and does not break unrelated functions.
3. **Given** an area the user is not authorized for, **When** reached, **Then** it shows a
   distinguishable unauthorized state (not a dead-end or a misleading empty result).
4. **Given** a broad degraded mode (multiple areas failing), **When** the portal loads, **Then** core
   navigation, search entry, and identity surface remain available.

### Edge Cases

- **Module disabled while a user is on its page**: The active page resolves to a clear state and the
  navigation no longer offers the module; the user is guided to a valid destination (no dead-end).
- **Permission revoked mid-session**: The next navigation/action re-evaluates rights server-side;
  newly unpermitted areas stop appearing and are refused if reached directly.
- **Direct URL to an unavailable/unauthorized/disabled area**: The shell renders the correct state
  (unauthorized, unavailable, or not-found) rather than a blank page or a leak of existence where
  that is sensitive.
- **Navigation source itself slow/unavailable**: The shell shows a loading/degraded navigation state
  while keeping already-known core entries usable; it does not block the whole portal.
- **Plugin contributes a malformed or failing navigation entry**: The failure is isolated; the rest
  of navigation and the portal remain usable (plugin failure must not break unrelated functions).
- **Conflicting navigation contributions**: Two extensions contributing to the same location resolve
  deterministically (per configured ordering) without duplicate or broken entries.
- **Deep link to a nested page**: Breadcrumbs and contextual navigation reconstruct orientation even
  when the user arrives without traversing ancestors.
- **Command Palette lists a now-invalid target**: Selecting a target that became unavailable/
  unpermitted resolves to the correct state rather than an error dead-end.
- **Keyboard shortcut conflicts**: Shortcut handling is consistent and does not trap focus or block
  accessibility; conflicts resolve predictably.
- **Theme change**: Switching themes changes shell presentation only; navigation structure,
  permissions, and functional states are unchanged.
- **Mobile**: No core navigation/search/AI/palette capability is unavailable solely because of a
  small screen.

## Requirements *(mandatory)*

### Functional Requirements

#### Global Shell
- **FR-001**: The portal MUST present a single persistent shell on every authenticated page,
  providing primary navigation and the identity and notification surface, so the portal is
  experienced as one coherent environment.
- **FR-002**: The shell MUST persist across navigation between modules, plugins, and pages without
  requiring a full context reset, keeping the user oriented.
- **FR-003**: Data surfaced from external services MUST be presented as integrated portal content,
  not as raw links out to separate applications.
- **FR-004**: The shell MUST present content using the shared Design System so modules and plugins
  look and behave consistently.

#### Navigation & Dynamic Assembly
- **FR-005**: Navigation MUST be assembled dynamically from the modules and plugins currently
  available and MUST update automatically when a module/plugin is enabled, disabled, or updated.
- **FR-006**: Navigation MUST be filtered by the current user's effective permissions, offering only
  entries the user is permitted to use (deny-by-default, evaluated server-side).
- **FR-007**: Disabling a module or plugin MUST remove its navigation entries and make its routes
  unreachable, without deleting its data.
- **FR-008**: Plugin navigation contributions (new pages, enrichment of existing modules/pages) MUST
  integrate into the existing navigation structure rather than forming a parallel menu.
- **FR-009**: Conflicting navigation contributions MUST resolve deterministically via configured
  ordering, with no duplicate or broken entries.
- **FR-010**: A failing or malformed navigation contribution MUST be isolated so the rest of
  navigation and the portal remain usable.

#### Pages, Breadcrumbs & Contextual Navigation
- **FR-011**: Every important page MUST allow the user to understand where they are, what they can
  do, what is happening, and the relevant next action.
- **FR-012**: The shell MUST provide breadcrumbs reflecting the hierarchical path, with navigable
  ancestors, including when a page is reached via a deep link.
- **FR-013**: Detail/context pages MUST offer contextual navigation to related objects and actions
  the user is permitted to use.
- **FR-014**: No page MUST present a dead-end empty state; a relevant next action MUST always be
  offered.

#### Global Search & AI Entry Points
- **FR-015**: Global search MUST be reachable from the shell on every page.
- **FR-016**: The AI MUST be reachable from the shell on every page and MUST run in parallel with
  classic search without blocking it or the rest of the portal.
- **FR-017**: Classic search results MUST be presentable without waiting for AI, and an AI outage
  MUST NOT render search or the shell unusable.
- **FR-018**: Search and AI entry points MUST respect the user's permissions and privacy; the shell
  MUST NOT surface results or actions the user is not permitted to access.

#### Command Palette & Keyboard Shortcuts
- **FR-019**: The portal MUST provide a Command Palette, openable via a keyboard shortcut from any
  page, offering navigation targets and actions scoped to the user's effective permissions.
- **FR-020**: The Command Palette MUST NOT offer actions the user is not permitted to perform, and
  any action reaching the server MUST still be independently authorized.
- **FR-021**: The portal MUST provide keyboard shortcuts for common navigation/actions that behave
  consistently across the portal and do not trap focus or impede accessibility.

#### Responsive & Mobile Navigation
- **FR-022**: The shell MUST adapt to screen size and remain functionally complete on mobile,
  exposing navigation, search, AI, and the Command Palette through mobile-appropriate patterns.
- **FR-023**: No core navigation/search/AI/palette capability MUST be unavailable solely because of a
  small screen.
- **FR-024**: Shell navigation MUST be fully operable with keyboard and touch, and accessibility
  preferences (e.g., reduced motion) MUST take precedence over visual effects.

#### Global States (Loading, Error, Degraded, Unauthorized)
- **FR-025**: The shell MUST render distinguishable functional states where relevant — loading,
  available, partial, stale, error, unavailable, maintenance, unauthorized, no data, syncing — for
  areas it hosts.
- **FR-026**: A slow or failing area MUST NOT block unrelated navigation or content; failures MUST be
  isolated to the affected area.
- **FR-027**: In degraded mode (multiple areas failing), core navigation, the global search entry,
  the AI entry where available, and the identity surface MUST remain available.
- **FR-028**: Reaching a disabled, unavailable, or unauthorized destination (including via direct
  URL) MUST resolve to the correct state rather than a blank page, and MUST NOT leak the existence of
  data where that existence is itself sensitive.

#### Permissions, Privacy & Theming Interaction
- **FR-029**: All shell navigation, Command Palette entries, and contextual actions MUST be gated by
  the authorization engine (deny-by-default, server-side) and MUST respect privacy preferences and
  admin visibility policies (permissions do not override privacy).
- **FR-030**: Permission or availability changes MUST take effect on the next evaluation so that
  navigation reflects current rights and module/plugin availability without manual reconfiguration.
- **FR-031**: Theme changes MUST affect only shell presentation; navigation structure, permissions,
  and functional-state meaning MUST be unchanged.

#### Events (shell-relevant)
- **FR-032**: The shell MUST react to availability/permission changes consumed from the relevant
  registries/events so navigation stays current; consumption MUST be idempotent where duplicate
  delivery is possible.

### Key Entities

- **Shell**: The persistent frame hosting all content; carries primary navigation, global search and
  AI entry points, identity and notification surface, and the Command Palette.
- **Navigation Model**: The dynamically assembled set of navigation entries derived from available
  modules/plugins and the user's effective permissions.
- **Navigation Entry**: A single navigable item (module, page, plugin contribution) with a location,
  ordering, and the permission/availability conditions under which it appears.
- **Breadcrumb Trail**: The hierarchical path to the current page with navigable ancestors.
- **Contextual Navigation**: Related objects/actions offered on a page, scoped to permissions.
- **Command Palette Entry**: A navigation target or action exposed in the palette, permission-scoped.
- **Keyboard Shortcut**: A binding from a key combination to a navigation/action.
- **Functional State**: The standardized state of a hosted area (loading, available, partial, stale,
  error, unavailable, maintenance, unauthorized, no data, syncing).
- **Module / Plugin (referenced)**: Availability sources whose enable/disable drives navigation;
  owned by the Extension/Module registries.
- **Permission/Policy (referenced)**: Authorization and privacy inputs that gate what the shell
  offers; owned by the Roles & Permissions and Privacy specs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The persistent shell (navigation, search entry, AI entry, identity/notification
  surface) is present on 100% of authenticated pages.
- **SC-002**: Enabling or disabling a module/plugin updates navigation automatically in 100% of cases
  with no manual menu editing; disabled areas appear in navigation in 0% of cases and are unreachable.
- **SC-003**: Navigation offers an entry the current user is not permitted to use in 0% of cases, and
  direct navigation to an unpermitted area yields an unauthorized state in 100% of cases.
- **SC-004**: Global search and AI are reachable from the shell on 100% of pages; classic search
  returns without waiting for AI in 100% of searches; an AI outage leaves search and navigation
  usable in 100% of cases.
- **SC-005**: The Command Palette lists only permitted targets/actions in 100% of cases; selecting an
  unpermitted action succeeds in 0% of cases.
- **SC-006**: Core navigation, search, AI, and the Command Palette are functionally complete on
  mobile in 100% of core tasks (no capability dropped solely due to screen size).
- **SC-007**: A slow or failing area blocks unrelated navigation/content in 0% of cases; in degraded
  mode, core navigation and the search/identity surface remain available in 100% of cases.
- **SC-008**: Every hosted area that is loading/unavailable/in-maintenance/unauthorized/stale shows a
  distinguishable state in 100% of applicable cases (no silent blank or dead-end).
- **SC-009**: Switching themes changes navigation structure, permissions, or functional-state meaning
  in 0% of cases.
- **SC-010**: A permission or availability change is reflected in navigation on the next evaluation
  in 100% of cases.

## Assumptions

- The internal content of specific modules (Home dashboard composition, Media catalog, etc.) is
  owned by their own detailed specs; this spec owns only the hosting shell and navigation.
- The search and AI engines are owned by their own specs; this spec owns the always-reachable entry
  points and the non-blocking/parallel behavior at the shell level.
- The authorization engine (Roles & Permissions) and the privacy/visibility engine are owned by
  their specs; the shell consumes their decisions and never overrides privacy.
- The set and defaults of keyboard shortcuts, and the exact Command Palette capabilities, follow the
  Design System and may be refined by UX without changing these rules. (Flagged as OQ-16.)
- "Available module/plugin" means registered and enabled per the Extension/Module registries; the
  registries themselves are owned by separate Core specs (Extension Registry / Connector Registry).

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation.

- **OQ-16 (Keyboard shortcut catalog)**: Confirm the baseline set of global keyboard shortcuts and
  whether users may customize them (and where that customization lives in the configuration
  hierarchy).
- **OQ-17 (Navigation ordering/grouping control)**: Confirm who controls navigation ordering and
  grouping (admin policy, user personalization within policy, or fixed), and how plugin contributions
  request placement.
- **OQ-18 (Public/unauthenticated shell)**: Confirm whether any shell/navigation is presented to
  unauthenticated visitors (e.g., a sign-in surface or public pages) or whether the shell is
  authenticated-only.
- **OQ-19 (Existence-leak policy)**: Confirm, for unauthorized direct navigation, when the shell must
  show "unauthorized" vs "not found" to avoid leaking the existence of sensitive objects.

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference) and the project
  Constitution (v1.0.0).
- Composes with: `specs/002-identity-users/spec.md` (identity surface, session) and
  `specs/003-roles-permissions/spec.md` (deny-by-default gating of navigation, palette, actions).
- Depends on / references: `architecture/FUNCTIONAL_ARCHITECTURE.md`, `ux/UX_PRINCIPLES.md`,
  `ux/DESIGN_SYSTEM.md`, `ux/THEMING.md`, `architecture/EVENT_MODEL.md`.
- Related specs (not owned here): Global Search and AI specs (engines), Home/Dashboard and each
  module's spec (hosted content), Extension Registry and Connector Registry specs (availability
  sources), and the Privacy spec (021) (visibility engine).
