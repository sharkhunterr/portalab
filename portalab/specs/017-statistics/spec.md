# Feature Specification: Statistics

**Feature Branch**: `017-statistics`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Detailed functional specification of the Statistics system."

## Role of This Document

This is a **detailed feature specification** for Statistics — the engine and surfaces that compute and
present admin/portal-defined statistics across domains, let users consume (choose/filter/period/
navigate/hide) but not freely author charts, gate certain statistics behind unlock conditions, and feed
other systems (dashboard, gamification, achievements, campaigns, newsletters, Wrapped, AI,
recommendations, leaderboards). It conforms to and refines the superior reference specification
(`specs/001-portal-global-spec/spec.md`) and composes with Roles & Permissions
(`specs/003-roles-permissions/spec.md`), Events & History (`specs/007-events-history/spec.md`), the
Dashboard (`specs/009-dashboard-widgets/spec.md`), Gamification & Economy
(`specs/013-gamification-economy/spec.md`), Campaigns (`specs/014-campaigns/spec.md`), and Marketplace
(`specs/015-marketplace/spec.md`), under the project Constitution (`.specify/memory/constitution.md`,
v1.0.0). It draws on `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`, and
`architecture/EVENT_MODEL.md`.

Scope boundary: this spec **owns** the statistics registry (admin/portal-defined definitions),
computation from history/events, consumption controls (choose/filter/period/navigate/hide), unlockable
statistics, cross-service statistics, and the provider interface that feeds other systems. It
**consumes** the event/history backbone (the authoritative source of the facts it aggregates), the
authorization/privacy engines (who may see what), and unlock sources (level/achievement from
Gamification, product from Marketplace, campaign from Campaigns). It does **not** own those domains'
data, the dashboard framework, or the AI engine — they consume Statistics. It chooses no technology and
contains no implementation detail.

### Authorship Rule (normative)

- **Statistics are defined by the portal/admin.** Users **MUST NOT** freely create their own charts or
  tables (no ad-hoc query/visualization builder in the product).
- **Users MAY**: choose among available statistics, filter, select a time period, navigate, and hide
  certain sections **where permitted** by policy.

This keeps statistics curated, consistent (shared Design System), privacy-safe, and comparable, rather
than an open BI tool.

**Terminology**: Statistic = an admin/portal-defined metric/visualization definition; Wrapped = a
periodic personal/community recap composed of statistics; Domain Event = a recorded fact; `occurred_at`
= real occurrence time.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consume admin-defined statistics: choose, filter, period, navigate, hide (Priority: P1)

A user browses the statistics available to them (defined by the portal/admin), chooses which to view,
applies filters, selects a time period, navigates between them, and hides sections where permitted —
without being able to author new charts/tables.

**Why this priority**: This is the core user interaction and encodes the locked authorship rule (curated
statistics, bounded consumption).

**Independent Test**: As a user, view the available statistics; apply a filter and a period; navigate
between statistics; hide a permitted section; attempt to create a custom chart and confirm there is no
such capability.

**Acceptance Scenarios**:

1. **Given** admin-defined statistics available to the user, **When** they browse, **Then** they can
   choose which to view from the available set only.
2. **Given** a statistic, **When** the user applies a filter and selects a period, **Then** the statistic
   updates accordingly within permitted ranges.
3. **Given** a hideable section, **When** the user hides it (where permitted), **Then** it is hidden and
   the preference persists; a non-hideable section cannot be hidden.
4. **Given** the statistics surfaces, **When** inspected, **Then** there is no free chart/table builder —
   users cannot author arbitrary visualizations.

### User Story 2 - Statistics computed from history/events, permission- and privacy-bounded (Priority: P1)

Statistics are computed from the event/history backbone and show only data the viewer is permitted to
see; a user's personal statistics reflect their own data, and aggregate/community statistics never
expose another user's private data by permission alone.

**Why this priority**: Correct, privacy-safe computation is foundational; statistics are a prime vector
for accidental data exposure.

**Independent Test**: Generate activity; view personal and aggregate statistics as users with different
permissions/visibility; confirm values match the historized facts and that private data is never exposed
by permission alone.

**Acceptance Scenarios**:

1. **Given** historized events, **When** a statistic is computed, **Then** it reflects those facts
   deterministically for the permitted scope.
2. **Given** a personal statistic, **When** viewed by its owner, **Then** it reflects their own data;
   **When** viewed by others, **Then** it respects the owner's visibility.
3. **Given** an aggregate/community statistic, **When** viewed, **Then** it does not expose another user's
   private data by permission alone (privacy honored independently of permission).

### User Story 3 - Domain coverage: Media/Playback/Reading/Gaming/Community/Gamification/Services/Requests/Users/Activity/Trends (Priority: P2)

The portal provides admin-defined statistics across all listed domains, each sourced from the relevant
domain's historized events via capabilities.

**Why this priority**: Breadth of coverage is the explicit requirement; statistics must reach every
listed domain while staying curated.

**Independent Test**: For each listed domain, confirm at least one admin-defined statistic exists,
computes from that domain's events, and respects permissions.

**Acceptance Scenarios**:

1. **Given** each domain (Media, Playback, Reading, Gaming, Community, Gamification, Services, Requests,
   Users, Activity, Trends), **When** statistics are viewed, **Then** permitted admin-defined statistics
   for that domain are available and computed from its events.
2. **Given** a domain source is unavailable, **When** a statistic is viewed, **Then** it shows a
   partial/stale/unavailable state rather than a fabricated value.

### User Story 4 - Cross-service statistics (Priority: P2)

Admin-defined statistics can combine data across multiple services/domains (e.g., total consumption
across media types) via capabilities, without coupling to a specific service.

**Why this priority**: Cross-service insight is a named differentiator and relies on capability-based
aggregation.

**Independent Test**: With two services/domains contributing to a capability, view a cross-service
statistic; confirm it aggregates both via the capability (not by service name) and reconciles to the
historized facts.

**Acceptance Scenarios**:

1. **Given** multiple services/domains providing a capability, **When** a cross-service statistic is
   computed, **Then** it aggregates them via the capability, not hard-coded service identities.
2. **Given** one contributing source is unavailable, **When** computed, **Then** the statistic indicates
   partial data rather than silently omitting or fabricating.

### User Story 5 - Unlockable statistics (level / Marketplace / achievement / campaign / combination) (Priority: P1)

Certain statistics are locked until the user meets an unlock condition — a level, a Marketplace
acquisition, an achievement, an active campaign, or a combination — enforced server-side.

**Why this priority**: Unlockable statistics are explicit and tie Statistics to Gamification/Marketplace/
Campaigns; enforcement must be server-side, not cosmetic.

**Independent Test**: Define locked statistics for each condition type and a combination; confirm each is
hidden/locked until the condition is met, unlocks when met, and that the gate is enforced server-side.

**Acceptance Scenarios**:

1. **Given** a statistic locked by level/achievement/Marketplace/campaign, **When** the user does not
   meet it, **Then** the statistic is locked (shown as lockable with the condition, or hidden per policy)
   and not computed/returned.
2. **Given** the unlock condition is met, **When** evaluated, **Then** the statistic unlocks and becomes
   viewable.
3. **Given** a combination condition, **When** evaluated, **Then** all parts must be met to unlock; the
   gate is enforced server-side (not UI-only).

### User Story 6 - Statistics engine feeds other systems (Priority: P1)

The statistics engine exposes computed results to dashboard widgets, gamification/achievements,
campaigns, newsletters, Wrapped, the AI, recommendations, and leaderboards — as the single authoritative
source, each consumer bounded by the end user's permissions.

**Why this priority**: Being the shared source for many consumers is the engine's structural role;
duplicated/inconsistent stat logic across consumers would violate principle XX.

**Independent Test**: Have a dashboard widget, a leaderboard, a newsletter, Wrapped, and the AI each
request a statistic; confirm all receive consistent values from the engine, each bounded by the end
user's permissions, with no consumer recomputing its own divergent version.

**Acceptance Scenarios**:

1. **Given** the statistics engine, **When** dashboard/gamification/achievements/campaigns/newsletters/
   Wrapped/AI/recommendations/leaderboards request data, **Then** they receive it from the engine as the
   single source, consistently.
2. **Given** a consumer requests a statistic for a user, **When** served, **Then** the result is bounded
   by that user's permissions and privacy.
3. **Given** two consumers request the same statistic, **When** served, **Then** they get consistent
   values (no divergent per-consumer recomputation).

### User Story 7 - Wrapped (periodic recap) (Priority: P2)

A user receives a periodic "Wrapped" recap composed of admin-defined statistics about their activity
over a period, respecting permissions/privacy, optionally delivered via newsletter/notification.

**Why this priority**: Wrapped is an explicitly named engagement feature built entirely on the statistics
engine.

**Independent Test**: Generate a Wrapped for a period; confirm it composes from admin-defined statistics
about the user, respects privacy, and can be delivered via the notification/newsletter path.

**Acceptance Scenarios**:

1. **Given** a period, **When** Wrapped is generated, **Then** it composes admin-defined statistics about
   the user for that period, bounded by permissions/privacy.
2. **Given** Wrapped, **When** delivered, **Then** it uses the notification/newsletter engine respecting
   preferences (Statistics provides data, Notifications delivers).
3. **Given** another user's data, **When** Wrapped is built, **Then** it is not exposed by permission
   alone.

### User Story 8 - Visualization, trends, and degraded states (Priority: P2)

Statistics render with appropriate visualizations (per the shared Design System), including trend views
over time, and show functional states (loading/partial/stale/unavailable) when a source is slow or
unavailable — never blocking unrelated statistics.

**Why this priority**: Consistent visualization and graceful degradation keep statistics trustworthy and
usable under partial failure.

**Independent Test**: View a trend statistic; make one source slow/unavailable; confirm that statistic
shows its state while others render, and that stale data is marked stale.

**Acceptance Scenarios**:

1. **Given** a trend statistic, **When** viewed, **Then** it shows change over the selected period using
   a consistent visualization.
2. **Given** a slow/unavailable source, **When** a statistic is viewed, **Then** it shows loading/partial/
   stale/unavailable and does not block unrelated statistics.
3. **Given** stale data, **When** shown, **Then** it is identifiable as stale (not presented as current).

### Edge Cases

- **User tries to author a chart**: There is no free chart/table builder; users only consume
  admin-defined statistics (choose/filter/period/navigate/hide).
- **Locked statistic accessed directly**: A locked statistic is not computed/returned until its condition
  is met; the gate is server-side (direct access does not bypass it).
- **Privacy vs aggregate**: Aggregate/community statistics never reveal an individual's private data by
  permission alone (e.g., small-sample aggregates must not de-anonymize). (See OQ-82.)
- **Source unavailable / partial**: Statistics show partial/stale/unavailable rather than fabricating or
  silently dropping data; cross-service stats indicate partial contribution.
- **Historical rule change**: Statistics derived from gamification/campaign rules reflect the historical
  rule version at each event's `occurred_at`; a rule change does not retroactively rewrite past values.
- **Reconstruction/replay**: Rebuilding a statistic from history is deterministic and does not re-emit
  one-off effects (consistent with Events & History).
- **Period boundaries & timezone**: Period selection uses defined boundaries/locale so "this month" is
  deterministic and consistent across consumers. (See OQ-81.)
- **Consumer divergence**: Consumers (dashboard, leaderboard, AI, Wrapped) receive values from the engine;
  they do not recompute divergent versions.
- **Permission change mid-view**: On next evaluation, a user who lost access to a statistic (e.g., locked
  product revoked) no longer sees it.
- **Unlock via campaign that ends**: A campaign-unlocked statistic locks again when the campaign ends
  unless another condition keeps it unlocked (per its unlock rule). (See OQ-83.)
- **Hidden section vs mandatory**: A section the admin marks non-hideable cannot be hidden by the user,
  consistent with dashboard policy.
- **Large/expensive statistic**: Heavy statistics are bounded (aggregation/caching) so they do not block
  the surface; freshness is indicated.

## Requirements *(mandatory)*

### Functional Requirements

#### Authorship & Consumption
- **FR-001**: Statistics MUST be defined by the portal/admin; the product MUST NOT provide a free chart/
  table/query builder for end users.
- **FR-002**: Users MUST be able to choose among available statistics, filter them, select a time period,
  and navigate between them, within permitted ranges.
- **FR-003**: Users MUST be able to hide sections where policy permits; non-hideable sections MUST NOT be
  hideable; hide preferences MUST persist.
- **FR-004**: Statistics MUST be presented using the shared Design System for consistency.

#### Computation, Permissions & Privacy
- **FR-005**: Statistics MUST be computed deterministically from the event/history backbone (the
  authoritative source of facts).
- **FR-006**: Statistics access MUST be gated by the authorization engine (deny-by-default, server-side)
  and MUST respect privacy/visibility; permission MUST NOT override privacy.
- **FR-007**: Personal statistics MUST reflect the owner's data and respect the owner's visibility when
  viewed by others; aggregate/community statistics MUST NOT expose an individual's private data by
  permission alone.
- **FR-008**: Statistics derived from versioned rules (gamification/campaign) MUST reflect the historical
  rule version at each event's `occurred_at`; a rule change MUST NOT retroactively rewrite past values.

#### Domain Coverage & Cross-Service
- **FR-009**: The portal MUST provide admin-defined statistics across at least: Media, Playback, Reading,
  Gaming, Community, Gamification, Services, Requests, Users, Activity, and Trends, each computed from the
  relevant domain's events.
- **FR-010**: The system MUST support cross-service statistics that aggregate multiple services/domains
  via capabilities, not hard-coded service identities.
- **FR-011**: When a contributing source is unavailable, a statistic MUST indicate partial/stale/
  unavailable state rather than fabricating or silently omitting data.

#### Unlockable Statistics
- **FR-012**: The system MUST support statistics locked by unlock conditions: level, Marketplace
  acquisition, achievement, active campaign, or a combination (all parts required).
- **FR-013**: A locked statistic MUST NOT be computed/returned until its condition is met; the gate MUST
  be enforced server-side (not UI-only).
- **FR-014**: When an unlock condition is met, the statistic MUST become viewable; when a time-bound
  condition (e.g., campaign) ends, the lock MUST reapply unless another condition keeps it unlocked.

#### Provider Interface (feeds other systems)
- **FR-015**: The statistics engine MUST expose computed results as the single authoritative source to:
  dashboard, gamification, achievements, campaigns, newsletters, Wrapped, AI, recommendations, and
  leaderboards.
- **FR-016**: Every result served to a consumer MUST be bounded by the end user's permissions and privacy.
- **FR-017**: Consumers MUST receive consistent values from the engine for the same statistic/scope/
  period; consumers MUST NOT recompute divergent versions (no parallel statistics logic — principle XX).

#### Wrapped
- **FR-018**: The system MUST support generating a periodic "Wrapped" recap composed of admin-defined
  statistics about the user for a period, bounded by permissions/privacy.
- **FR-019**: Wrapped delivery MUST use the notification/newsletter engine respecting preferences
  (Statistics provides data; Notifications delivers).

#### Visualization, Trends, Degraded States
- **FR-020**: Statistics MUST support trend views over a selected period and MUST render functional states
  (loading, partial, stale, unavailable) where relevant.
- **FR-021**: A slow/unavailable source MUST NOT block unrelated statistics; stale data MUST be
  identifiable as stale.

#### Events, History, Observability
- **FR-022**: Statistics computation MUST consume events idempotently using `occurred_at`; reconstruction
  of a statistic from history MUST be deterministic and MUST NOT re-emit one-off effects.
- **FR-023**: Statistic definitions and unlock conditions MUST be versioned/auditable; defining or
  changing statistics MUST be a permissioned, audited admin action.
- **FR-024**: Heavy statistics MUST be bounded (e.g., aggregation/caching) so they do not block surfaces;
  when cached, freshness/staleness MUST be indicated.
- **FR-025**: No statistic or export MUST expose secrets; period/filter semantics MUST be deterministic
  and consistent across consumers.

### Statistics Domain Catalog (illustrative)

Each is admin/portal-defined, computed from historized events via capabilities, permission/privacy
bounded:

- **Media / Playback**: watch counts/time, finished items, genres, peak times.
- **Reading**: books/articles read, reading time, genres.
- **Gaming**: sessions, playtime, titles, genres.
- **Community**: projects, votes cast, participation, help provided.
- **Gamification**: XP/Contribution/Coins trends, achievements unlocked, quests completed, level
  progression.
- **Services**: availability/uptime trends, incidents over time (permission-gated infra detail).
- **Requests**: request volume, fulfillment, quota usage (no priority metric — consistent with
  Marketplace).
- **Users**: active users, onboarding completion, retention (aggregate, privacy-safe).
- **Activity**: overall activity over time, Since-Last-Login deltas.
- **Trends**: period-over-period change for any of the above.
- **Cross-service**: totals combining media types / services via capabilities.

### Consumer/Provider Model

The engine is the **single source**; consumers request statistics bounded by the end user's permissions:

- Dashboard widgets, Leaderboards, Gamification/Achievements, Campaigns, Newsletters, Wrapped, AI,
  Recommendations.

### Key Entities

- **Statistic Definition**: An admin/portal-defined metric/visualization (source events/capability,
  aggregation, visualization type, filters/periods allowed, unlock condition, version).
- **Statistic Result**: A computed value/series for a scope (user/community) and period, bounded by
  permissions.
- **Unlock Condition**: level / Marketplace acquisition / achievement / campaign / combination gating a
  statistic.
- **Filter / Period**: User-selectable refinement within permitted ranges.
- **Hideable Section**: A section a user may hide where policy permits.
- **Wrapped**: A periodic recap composed of statistics for a user/community over a period.
- **Provider Interface**: The contract exposing results to consumers consistently.
- **Permission/Privacy/Event-History (referenced)**: Gating and source of facts, owned elsewhere.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: End users author arbitrary charts/tables in 0% of cases (no free builder); they can choose/
  filter/period/navigate/hide within policy in 100% of permitted cases.
- **SC-002**: Statistics reflect the historized facts deterministically in 100% of defined cases.
- **SC-003**: Aggregate/community statistics expose an individual's private data by permission alone in
  0% of cases.
- **SC-004**: Admin-defined statistics exist and compute for 100% of the listed domains (Media/Playback/
  Reading/Gaming/Community/Gamification/Services/Requests/Users/Activity/Trends).
- **SC-005**: A locked statistic is computed/returned before its condition is met in 0% of cases; the gate
  is server-side in 100% of cases.
- **SC-006**: Consumers (dashboard/gamification/achievements/campaigns/newsletters/Wrapped/AI/
  recommendations/leaderboards) receive values from the engine in 100% of cases; divergent per-consumer
  recomputation occurs in 0% of cases.
- **SC-007**: Every result served to a consumer is bounded by the end user's permissions/privacy in 100%
  of cases.
- **SC-008**: A rule change retroactively rewrites historical statistic values in 0% of cases (historical
  rule version applied in 100% of reconstructions).
- **SC-009**: A slow/unavailable source blocks unrelated statistics in 0% of cases; stale data is marked
  stale in 100% of cases.
- **SC-010**: Cross-service statistics aggregate via capabilities (not service identity) in 100% of cases;
  partial contribution is indicated in 100% of partial cases.

## Assumptions

- The event/history backbone is the authoritative source of facts; Statistics aggregates it and does not
  own domain data.
- Unlock sources are owned elsewhere: level/achievement (Gamification), product (Marketplace), campaign
  (Campaigns); Statistics evaluates the condition and gates accordingly.
- The dashboard framework, newsletters/notification delivery, and the AI engine are owned by their specs;
  they consume the Statistics provider interface.
- The exact statistic definitions, aggregation methods, and visualization choices are admin/portal
  configuration consistent with the Design System. (Flagged as OQ-80.)
- Privacy-safe aggregation (minimum sample sizes / anonymization) is required but its thresholds are
  policy. (Flagged as OQ-82.)

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation.

- **OQ-80 (Definition authorship scope)**: Confirm whether only the single Admin defines statistics or
  certain roles (e.g., Editor) may, and whether plugins may contribute statistic definitions (they can
  per Extensibility — confirm the governance).
- **OQ-81 (Period/timezone semantics)**: Confirm period boundary and timezone rules (user locale vs portal
  time) so periods are deterministic and consistent across consumers.
- **OQ-82 (Privacy-safe aggregation)**: Confirm minimum-sample/anonymization thresholds that prevent
  aggregate statistics from de-anonymizing individuals.
- **OQ-83 (Unlock re-lock behavior)**: Confirm whether an unlocked statistic ever re-locks (e.g., when a
  campaign ends or a Marketplace access is revoked) and the precise re-evaluation rule.
- **OQ-84 (Freshness/caching expectations)**: Confirm the freshness guarantee (real-time vs periodic) for
  heavy statistics and how staleness is surfaced.

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference) and the project
  Constitution (v1.0.0).
- Composes with: `specs/003-roles-permissions/spec.md` (`statistics.read`/`statistics.manage`; gating),
  `specs/007-events-history/spec.md` (authoritative facts; idempotency; reconstruction; rule versioning),
  `specs/009-dashboard-widgets/spec.md` (statistic widgets), `specs/013-gamification-economy/spec.md`
  (XP/Contribution/Coins stats; level/achievement unlocks), `specs/014-campaigns/spec.md` (campaign
  unlocks), and `specs/015-marketplace/spec.md` (Marketplace-unlocked statistics; requests/quota stats
  without priority).
- Depends on / references: `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`,
  `architecture/EVENT_MODEL.md`, `architecture/DATA_MODEL.md`, `ux/DESIGN_SYSTEM.md`.
- Related specs (not owned here): AI (recommendations/consumption), Notifications/Newsletters (Wrapped
  delivery), Media/Services and other domains (source events via capabilities), and the Privacy spec (021)
  (visibility engine and anonymization).
