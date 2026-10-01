# Feature Specification: Dashboard & Widget System

**Feature Branch**: `009-dashboard-widgets`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Detailed functional specification of the Dashboard & Widget System."

## Role of This Document

This is a **detailed feature specification** for the Dashboard & Widget System — the personalized Home
surface composed of independently-loading widgets, including the starter dashboard, administrative
policies, and the "Since Last Login" summary. It conforms to and refines the superior reference
specification (`specs/001-portal-global-spec/spec.md`) and composes with Roles & Permissions
(`specs/003-roles-permissions/spec.md`), the Portal Core shell (`specs/004-portal-core-shell/spec.md`),
Services & Health (`specs/006-services-health/spec.md`), and Events & History
(`specs/007-events-history/spec.md`), under the project Constitution
(`.specify/memory/constitution.md`, v1.0.0). It draws on `product/PRODUCT_BLUEPRINT.md`,
`ux/UX_PRINCIPLES.md`, `ux/DESIGN_SYSTEM.md`, and `ux/THEMING.md`.

Scope boundary: this spec owns the **dashboard composition and widget framework** — how widgets are
added/removed/hidden/ordered/resized/configured within policy, layouts and responsiveness, the starter
dashboard, Marketplace-provided widgets, admin widget policies (free/default/mandatory/locked/
conditional/disabled), the per-widget functional states, and the "Since Last Login" summary. It does
**not** own the internal domain logic each widget visualizes (Media playback, News, Gamification,
Services health, Community, Marketplace, etc.) — widgets consume those domains. It does not own the
authorization engine, the theming engine, or the event/history store — it composes with them. It
chooses no technology and contains no implementation detail.

**Terminology**: *Widget* = a reusable dashboard unit presenting a slice of a domain; *Layout* = the
arrangement of widgets; *Functional state* = the standardized state of a widget's data (loading,
available, partial, stale, error, unavailable, etc.); Domain Event = a recorded fact.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Independently-loading dashboard resilient to outages (Priority: P1)

A user opens Home and sees their widgets, each loading independently; a slow or failing widget (e.g.,
one backed by an unavailable external service) shows its own state while every other widget and the
rest of the dashboard remain usable.

**Why this priority**: "Widgets load independently" and "the dashboard stays usable when an external
service is unavailable" are explicit, locked requirements and the core resilience promise of Home.

**Independent Test**: Load a dashboard with several widgets, one backed by an unavailable service;
confirm the healthy widgets render normally while the affected one shows unavailable/error, and the
dashboard remains fully usable.

**Acceptance Scenarios**:

1. **Given** a dashboard with multiple widgets, **When** Home loads, **Then** each widget loads
   independently and a slow/failing widget does not block the others.
2. **Given** a widget whose backing service is unavailable, **When** Home loads, **Then** that widget
   shows an unavailable/error state while unrelated widgets display normally.
3. **Given** a partial failure across several widgets, **When** Home loads, **Then** the dashboard
   remains usable and each affected widget shows its own functional state.

### User Story 2 - Personalize the dashboard within policy (Priority: P1)

A user adds, removes, hides, reorders, resizes, and configures widgets within administrative policy;
changes persist and are honored on return.

**Why this priority**: Personalization bounded by policy is a defining dashboard capability and a
locked rule (personalization is bounded by security/privacy/business rules).

**Independent Test**: Add a widget, remove another, hide a third, reorder, resize, and configure a
widget; reload and confirm all changes persisted and were honored, and that policy limits were
respected.

**Acceptance Scenarios**:

1. **Given** available widgets, **When** the user adds one, **Then** it appears on the dashboard and
   the change persists.
2. **Given** a widget on the dashboard, **When** the user removes or hides it, **Then** it is removed/
   hidden and the change persists (hiding keeps it available to re-add; removing takes it off the
   layout).
3. **Given** widgets, **When** the user reorders or resizes them, **Then** the new order/size persists.
4. **Given** a configurable widget, **When** the user changes its configuration, **Then** the
   configuration persists and is reflected on next load.
5. **Given** any personalization action, **When** it would violate an admin policy, **Then** it is
   refused with a clear reason.

### User Story 3 - Admin widget policies: free, default, mandatory, locked, conditional, disabled (Priority: P1)

An administrator sets per-widget policies that govern user personalization: free (user choice),
default (present unless removed), mandatory (cannot be removed), locked (cannot be moved/resized/
reconfigured), conditional (shown only when a condition holds), and disabled (unavailable to users).

**Why this priority**: These exact policy classes are specified in the Blueprint and determine what
personalization is even permitted.

**Independent Test**: For each policy class, configure a widget and confirm user personalization is
constrained accordingly (e.g., mandatory cannot be removed, locked cannot be moved, disabled does not
appear, conditional appears only when its condition holds).

**Acceptance Scenarios**:

1. **Given** a mandatory widget, **When** the user tries to remove it, **Then** removal is refused.
2. **Given** a locked widget, **When** the user tries to move/resize/reconfigure it, **Then** the
   change is refused while the widget still displays.
3. **Given** a disabled widget, **When** the dashboard renders, **Then** it is not available to the
   user at all.
4. **Given** a conditional widget, **When** its condition is met, **Then** it appears; **When** not
   met, **Then** it does not appear.
5. **Given** a default widget, **When** a new user onboards, **Then** it is present initially and MAY
   be removed by the user unless also mandatory.
6. **Given** any admin policy, **When** it conflicts with a stored user preference, **Then** policy
   takes precedence while the user's underlying preference is retained for restoration if the policy
   is relaxed.

### User Story 4 - Automatic starter dashboard at onboarding (Priority: P1)

A new user completes onboarding and arrives at an automatically configured starter dashboard — a
usable, policy-compliant set of widgets — without manual setup.

**Why this priority**: The automatic starter dashboard is explicitly required and is the user's first
impression of the "one environment".

**Independent Test**: Complete onboarding as a new user; confirm a starter dashboard is present,
policy-compliant (includes mandatory/default widgets), and usable with no dead-ends.

**Acceptance Scenarios**:

1. **Given** a newly onboarded user, **When** they reach Home, **Then** a starter dashboard is already
   configured within policy (including mandatory and default widgets).
2. **Given** the starter dashboard, **When** the user personalizes it, **Then** changes are allowed
   within policy and persist.

### User Story 5 - Since Last Login summary (Priority: P2)

A returning user sees a "Since Last Login" summary of relevant changes (new events, media, news,
progression, service changes, community activity) scoped to their permissions and privacy.

**Why this priority**: "Since Last Login" is an explicitly named Home capability that re-orients
returning users.

**Independent Test**: Generate activity between two logins; confirm the summary reflects relevant
changes since last login, scoped to permissions/privacy, with a relevant next action (no dead-end).

**Acceptance Scenarios**:

1. **Given** activity occurred since the user's last login, **When** they return, **Then** a "Since
   Last Login" summary presents relevant changes they are permitted to see.
2. **Given** no relevant activity, **When** they return, **Then** the summary shows a clear state with a
   relevant next action (not a dead-end).
3. **Given** private data of others, **When** the summary is built, **Then** it is not surfaced by
   permission alone.

### User Story 6 - Marketplace-provided widgets (Priority: P2)

A user can obtain widgets via the Marketplace; an acquired widget becomes available to add to the
dashboard (activating immediately where applicable), integrating into the same widget framework and
policies.

**Why this priority**: Widgets are a named Marketplace product type and part of the extensible,
convergent Marketplace.

**Independent Test**: Acquire a widget from the Marketplace; confirm it becomes available to add,
integrates into the framework (states, policies, responsive), and is governed by the same rules as
built-in widgets.

**Acceptance Scenarios**:

1. **Given** a Marketplace widget product, **When** the user acquires it, **Then** it becomes available
   to add (activating immediately unless explicit configuration is required).
2. **Given** an acquired widget, **When** placed on the dashboard, **Then** it behaves like any widget
   (states, policy, responsive, configuration).
3. **Given** a widget is later removed from Marketplace availability, **When** an existing owner uses
   it, **Then** they keep access (per Marketplace archive rules).

### User Story 7 - Responsive layouts across screen sizes (Priority: P2)

The dashboard adapts widget layout to screen size and remains functionally complete on mobile; widgets
reflow without losing content or capability.

**Why this priority**: "Mobile remains functionally complete" and responsiveness are locked UX
principles; a dashboard that breaks on mobile would violate them.

**Independent Test**: View the dashboard at phone, tablet, and desktop sizes; confirm widgets reflow
appropriately, remain usable, and that no widget's core capability is lost solely due to screen size.

**Acceptance Scenarios**:

1. **Given** a dashboard, **When** viewed at different screen sizes, **Then** the layout reflows
   appropriately and remains usable.
2. **Given** a small screen, **When** the dashboard renders, **Then** widgets remain functionally
   complete (no core capability dropped solely due to size).
3. **Given** accessibility preferences (reduced motion, keyboard), **When** personalizing/viewing the
   dashboard, **Then** all functions remain operable and preferences take precedence over visual
   effects.

### User Story 8 - Presentation independent from functional state (Priority: P1)

A widget's functional state (loading, available, partial, stale, error, unavailable, etc.) carries the
same meaning regardless of theme or personalization; themes change only appearance, never the
functional truth a widget conveys.

**Why this priority**: "Visual presentation must remain totally independent of functional state" is an
explicit requirement and a locked principle (functional state vs presentation).

**Independent Test**: Put a widget into each functional state; switch themes and personalization;
confirm the state's meaning is unchanged and accessibility remains effective — only appearance differs.

**Acceptance Scenarios**:

1. **Given** a widget in a given functional state, **When** the theme changes, **Then** the state's
   meaning is unchanged (only its appearance may differ).
2. **Given** a widget showing stale data, **When** any theme/personalization is applied, **Then** the
   data is still identifiable as stale.
3. **Given** an unavailable/error widget, **When** themed, **Then** it still communicates
   unavailable/error (presentation never masks or alters functional truth).

### Edge Cases

- **Backing service unavailable**: The widget shows unavailable/error with its own state; the rest of
  the dashboard stays usable; the dashboard never fails as a whole because one service is down.
- **Slow widget**: Shows loading while others render; it never blocks the dashboard or other widgets.
- **Stale data**: A widget presenting cached/last-known data marks it stale; staleness survives theme
  changes.
- **Partial data**: A widget with some sections available and others not shows a partial state rather
  than all-or-nothing.
- **Mandatory + user removal attempt**: Refused with a clear reason; the widget remains.
- **Locked widget drag/resize/config attempt**: Refused; the widget still displays its data.
- **Conditional widget condition flips at runtime**: It appears/disappears as the condition changes,
  without breaking the layout.
- **Disabled widget referenced in a saved layout**: It does not render; the layout degrades gracefully
  (no broken slot), and may be restorable if re-enabled.
- **Policy change after user personalization**: New policy takes precedence; the user's prior
  preference is retained for restoration if the policy is later relaxed (never silently erased).
- **Marketplace widget requiring configuration**: Available after acquisition but shows a
  needs-configuration state until configured (does not auto-activate if explicit config required).
- **Permission revoked for a widget's data**: The widget stops showing that data on next evaluation
  (server-side), independent of its placement.
- **Private data in Since Last Login**: Never surfaced by permission alone; privacy honored.
- **Empty dashboard**: Not a dead-end — offers to add widgets / restores starter defaults within
  policy.
- **Widget failure (plugin/Marketplace)**: Isolated; a failing widget never breaks unrelated widgets
  or the dashboard (plugin isolation).
- **Theme change mid-session**: Only appearance changes; order, sizes, states, and data meaning are
  unchanged.

## Requirements *(mandatory)*

### Functional Requirements

#### Dashboard Composition & Independent Loading
- **FR-001**: The Home dashboard MUST be composed of widgets that each load independently so a slow or
  failing widget does not block the others.
- **FR-002**: The dashboard MUST remain usable when one or more backing external services are
  unavailable; a single failure MUST NOT fail the dashboard as a whole.
- **FR-003**: Each widget MUST render its own functional state and MUST NOT depend on another widget's
  success to render.

#### Personalization (add/remove/hide/order/size/configure)
- **FR-004**: Users MUST be able to add and remove widgets within administrative policy, with changes
  persisted.
- **FR-005**: Users MUST be able to hide a widget (keeping it available to re-add) distinct from
  removing it from the layout.
- **FR-006**: Users MUST be able to reorder and resize widgets within policy, with changes persisted.
- **FR-007**: Users MUST be able to configure configurable widgets within policy, with configuration
  persisted and reflected on next load.
- **FR-008**: Personalization MUST be bounded by administrative policy, security, privacy, and business
  rules; a disallowed action MUST be refused with a clear reason.

#### Admin Widget Policies
- **FR-009**: Administrators MUST be able to set per-widget policy classes: free, default, mandatory,
  locked, conditional, and disabled.
- **FR-010**: A mandatory widget MUST NOT be removable by the user; a locked widget MUST NOT be
  movable/resizable/reconfigurable by the user while still displaying.
- **FR-011**: A disabled widget MUST NOT be available to users; a conditional widget MUST appear only
  when its condition holds.
- **FR-012**: A default widget MUST be present initially and MAY be removed by the user unless also
  mandatory.
- **FR-013**: When an admin policy conflicts with a stored user preference, policy MUST take precedence
  while the user's underlying preference is retained for restoration if the policy is later relaxed.

#### Starter Dashboard
- **FR-014**: Onboarding MUST result in an automatically configured starter dashboard within policy,
  including mandatory and default widgets, usable with no dead-ends.
- **FR-015**: The user MUST be able to personalize the starter dashboard within policy, with changes
  persisted.

#### Since Last Login
- **FR-016**: The dashboard MUST provide a "Since Last Login" summary of relevant changes since the
  user's previous session, scoped to the user's permissions and privacy.
- **FR-017**: When there is no relevant activity, the summary MUST present a clear state with a relevant
  next action (no dead-end).
- **FR-018**: The summary MUST NOT surface another user's Private data by permission alone.

#### Marketplace Widgets
- **FR-019**: Widgets acquired via the Marketplace MUST become available to add, activating immediately
  unless explicit configuration is required (then shown as needs-configuration until configured).
- **FR-020**: Marketplace/plugin widgets MUST integrate into the same framework (states, policies,
  responsive, configuration) and MUST follow Marketplace archive rules (existing owners keep access).
- **FR-021**: A failing Marketplace/plugin widget MUST be isolated and MUST NOT break unrelated widgets
  or the dashboard.

#### Responsive & Accessibility
- **FR-022**: The dashboard MUST adapt widget layout to screen size and MUST remain functionally
  complete on mobile (no core capability dropped solely due to size).
- **FR-023**: Dashboard personalization and viewing MUST be operable with keyboard and touch, and
  accessibility preferences MUST take precedence over visual effects.

#### Functional States
- **FR-024**: Each widget MUST be able to present the standardized functional states where relevant:
  loading, available, partial, stale, error, unavailable (and, where applicable, maintenance,
  unauthorized, no data, syncing).
- **FR-025**: Stale data MUST be identifiable as stale; partial data MUST be shown as partial rather
  than all-or-nothing; error/unavailable MUST be actionable, not silent.

#### Presentation vs Functional State
- **FR-026**: A widget's functional state MUST carry the same meaning regardless of theme or
  personalization; themes MUST change only appearance, never functional truth.
- **FR-027**: No theme or personalization MUST render a widget's critical information
  (including its functional state) inaccessible.

#### Permissions, Privacy & Events
- **FR-028**: Widget availability and data MUST be gated by the authorization engine (deny-by-default,
  server-side) and MUST respect privacy and admin visibility policies (permissions do not override
  privacy).
- **FR-029**: A permission or availability change MUST take effect on the next evaluation so widgets
  reflect current rights and policy.
- **FR-030**: Widgets MUST consume data via each domain's defined contract/capability (not hard-coded to
  a specific external service), consistent with capability-based integration.
- **FR-031**: The dashboard MAY react to domain events to refresh widgets; consumption MUST be
  idempotent where duplicate delivery is possible, and no secrets MUST be exposed in widget data.

### Important Widgets (catalog)

Each widget consumes its domain via that domain's contract and presents standardized functional
states; data is permission/privacy scoped. The required set includes at least:

- **Current Playback** — media currently playing (consumes Media/Services capabilities).
- **Events** — recent/upcoming activity from the event backbone (consumes Events/History).
- **News** — latest editorial items (consumes News).
- **Featured News** — highlighted editorial items (consumes News).
- **Upcoming Content** — requested/soon-available media and scheduled items (consumes Media/Calendar).
- **Progression** — the user's XP/Contribution/Level progress (consumes Gamification).
- **Services** — service availability overview (consumes Services & Health).
- **Health** — infrastructure/health summary where permitted (consumes Services & Health; privileged
  detail gated by permission).
- **Community** — community activity/projects within visibility (consumes Community).
- **Achievements** — recent/near achievements (consumes Gamification).
- **Marketplace** — relevant Marketplace items/offers (consumes Marketplace).

### Widget Policy Model

**Policy classes**: free, default, mandatory, locked, conditional, disabled.

- **free**: user may add/remove/move/resize/configure freely (within other rules).
- **default**: present on new/starter dashboards; removable unless also mandatory.
- **mandatory**: cannot be removed; may still be movable/resizable unless also locked.
- **locked**: cannot be moved/resized/reconfigured; still displays.
- **conditional**: visible only while a defined condition holds.
- **disabled**: not available to users at all.

**Invariants**:
- Policy precedence over user preference; user preference retained for restoration.
- A widget may combine compatible classes (e.g., mandatory + locked); disabled overrides presence.
- Disabled/absent widgets never leave a broken layout slot.

### Widget Functional State Model

**States**: loading, available, partial, stale, error, unavailable (plus maintenance, unauthorized,
no data, syncing where applicable).

**Invariants**:
- Exactly one primary functional state is conveyed per widget at a time (sub-sections may carry their
  own state for partial).
- Functional-state meaning is independent of theme/personalization.
- Stale is always identifiable; error/unavailable is always actionable (not silent).

### Key Entities

- **Dashboard**: A user's personalized Home composition (ordered, sized, configured widgets) within
  policy.
- **Widget**: A reusable unit presenting a slice of a domain, with size, position, configuration, and a
  functional state.
- **Widget Definition**: The available widget type (built-in, plugin, or Marketplace) with its
  configuration schema and default policy.
- **Layout**: The arrangement (order, size, placement) of widgets, responsive across screen sizes.
- **Widget Policy**: The admin-set class (free/default/mandatory/locked/conditional/disabled) governing
  personalization.
- **User Dashboard Preference**: The user's stored choices, retained even when overridden by policy.
- **Since Last Login Summary**: A permission/privacy-scoped digest of relevant changes since last
  session.
- **Functional State**: The standardized widget state (see model).
- **Permission/Policy/Theme (referenced)**: Authorization/privacy gating and presentation, owned by
  their respective specs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A slow/failing widget blocks other widgets or the dashboard in 0% of cases; the dashboard
  stays usable when a backing service is unavailable in 100% of cases.
- **SC-002**: Add/remove/hide/reorder/resize/configure changes persist and are honored on reload in
  100% of cases within policy.
- **SC-003**: Each admin policy class constrains personalization exactly as defined in 100% of cases
  (mandatory not removable, locked not movable, disabled absent, conditional condition-gated).
- **SC-004**: A policy override erases the user's underlying preference in 0% of cases (retained for
  restoration in 100%).
- **SC-005**: 100% of newly onboarded users arrive at a usable, policy-compliant starter dashboard with
  no dead-ends.
- **SC-006**: The Since Last Login summary surfaces data beyond the user's permissions/privacy in 0% of
  cases.
- **SC-007**: Marketplace/plugin widgets integrate with full framework behavior (states, policy,
  responsive) in 100% of cases; a failing such widget breaks unrelated widgets in 0% of cases.
- **SC-008**: The dashboard remains functionally complete on mobile in 100% of core tasks (no capability
  dropped solely due to screen size).
- **SC-009**: A theme change alters a widget's functional-state meaning in 0% of cases; stale data
  remains identifiable as stale across 100% of themes.
- **SC-010**: Each widget presents a distinguishable functional state (loading/partial/stale/error/
  unavailable) in 100% of applicable cases (no silent blank).

## Assumptions

- The domain logic each widget visualizes (Media, News, Gamification, Services & Health, Community,
  Marketplace, Calendar, Events) is owned by those domains' specs; widgets consume their contracts.
- The authorization engine, privacy/visibility engine, theming engine, and event/history store are
  owned by their specs; the dashboard composes with them.
- The exact grid/layout mechanics and the number of responsive breakpoints are UX/plan decisions; this
  spec fixes behavior (reflow, mobile completeness), not a specific grid. (Flagged as OQ-41.)
- "Hide" vs "remove": hiding keeps the widget available to re-add without losing its configuration;
  removing takes it off the layout. (Confirm exact semantics — OQ-40.)
- The baseline required widget set is the catalog above; additional widgets may be added via plugins/
  Marketplace without changing these rules.
- "Since Last Login" relevance (which event types, how far back) is configurable policy consistent with
  Privacy. (Flagged as OQ-42.)

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation.

- **OQ-40 (Hide vs remove semantics)**: Confirm the precise distinction and persistence between hiding
  a widget (retains config, re-addable) and removing it (off the layout), and whether mandatory widgets
  can be hidden.
- **OQ-41 (Layout model & breakpoints)**: Confirm the layout model (free grid vs fixed columns) and how
  many responsive breakpoints/behaviors are required, and whether users may save multiple layouts.
- **OQ-42 (Since Last Login scope)**: Confirm which event/change types feed the summary, the lookback
  window, and how "last login" is defined for frequent/concurrent sessions.
- **OQ-43 (Conditional widget conditions)**: Confirm the catalog of conditions available for
  conditional widgets (role, service availability, campaign active, data presence, etc.).
- **OQ-44 (Widget data refresh model)**: Confirm how widgets refresh (event-driven vs periodic vs
  on-view) and the freshness/staleness thresholds that drive the stale state.

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference) and the project
  Constitution (v1.0.0).
- Composes with: `specs/003-roles-permissions/spec.md` (widget/data gating; privacy composition),
  `specs/004-portal-core-shell/spec.md` (Home hosted in the shell; functional-state presentation,
  degraded mode), `specs/006-services-health/spec.md` (Services/Health widgets), and
  `specs/007-events-history/spec.md` (Events/Since-Last-Login/refresh via events).
- Depends on / references: `product/PRODUCT_BLUEPRINT.md`, `ux/UX_PRINCIPLES.md`, `ux/DESIGN_SYSTEM.md`,
  `ux/THEMING.md`, `architecture/DATA_MODEL.md`.
- Related specs (not owned here): Media, News, Calendar, Community, Gamification, and Marketplace
  (widget data sources), the Personalization/Themes/A11y spec (022) (presentation), and the Privacy spec (021) (visibility engine).
