# Feature Specification: Personal Extensible Portal — Global Functional Specification

**Feature Branch**: `001-portal-global-spec`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Global functional specification of the Personal Extensible Portal — the superior reference specification governing all detailed feature specs."

## Role of This Document

This is the **superior reference specification** for the Personal Extensible Portal. Every
detailed feature specification produced later MUST conform to this document, which in turn
conforms to `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`,
`decisions/DECISIONS.md`, and the project Constitution (`.specify/memory/constitution.md`).

It defines **WHAT** the portal does and **WHY**, across all domains. It does not choose any
technology and does not describe implementation. Where the existing product documentation is
genuinely ambiguous, the ambiguity is flagged (see "Open Questions & Flagged Ambiguities")
rather than resolved by invention.

**Terminology note (OQ-1 — RESOLVED, see CD-009 in `decisions/CANONICAL_DECISIONS.md`):** the word
"Event" was overloaded in the source documentation. The canonical vocabulary is now fixed and used
consistently across all specs:
- **Domain Event** = a recorded fact that something happened (e.g., `media.playback_started`).
- **Campaign** = a time-bound themed operation (e.g., Halloween) with multipliers, quests,
  achievements, themes. (The source's "Event/Campaign" means Campaign.)
- **Automation** = a configurable WHEN→IF→THEN reaction.
These three are distinct concepts and are named distinctly throughout.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unified entry point to a digital environment (Priority: P1)

A returning user opens the portal and, from a single coherent environment, sees what changed
since their last login, the status of their services, their media and progression, and can
navigate directly to any area or act on any object — without needing to understand the
underlying technical architecture.

**Why this priority**: This is the product's reason to exist (the "one environment, not a
collection of links" principle). Without it there is no portal; every other capability hangs
off this unified surface.

**Independent Test**: Authenticate as an existing user with at least one connected service
and prior activity; confirm the Home dashboard loads independently-loading widgets, a
"Since Last Login" summary, service status, and working navigation to each enabled module,
with no dead-end empty states.

**Acceptance Scenarios**:

1. **Given** an authenticated user with a configured dashboard, **When** they open Home,
   **Then** each widget loads independently and a slow or failing widget does not block the
   others.
2. **Given** a user returning after prior activity, **When** Home loads, **Then** a
   "Since Last Login" summary of relevant changes is presented.
3. **Given** any enabled module, **When** the user navigates to it, **Then** the page conveys
   where they are, what they can do, what is happening, and a relevant next action.

### User Story 2 - Capability-based service integration with graceful degradation (Priority: P1)

An administrator connects an external service through a connector; its capabilities become
available to modules. When the service is slow, unavailable, or in maintenance, the portal
remains usable and clearly communicates the degraded state while preserving previously
historized data.

**Why this priority**: Capability-based integration and graceful degradation are core
differentiators; modules depend on capabilities, not concrete services, so the system can
grow without rewrites and survive partial outages.

**Independent Test**: Register a service exposing a capability consumed by a module; verify
the module uses it without referencing the service by name; then simulate the service being
unavailable and confirm the module shows an "unavailable" state while unrelated functions and
existing history remain intact.

**Acceptance Scenarios**:

1. **Given** a module that consumes a capability, **When** two different services provide that
   capability, **Then** the module functions with either without module changes.
2. **Given** a connected service goes unavailable, **When** a user views a dependent surface,
   **Then** the surface shows a distinguishable degraded state and does not break unrelated
   functions.
3. **Given** a service is disconnected, **When** the user views history that originated from
   it, **Then** the historized representation remains available (live access/sync stops, history
   is not auto-erased).

### User Story 3 - The product loop: action to event to history to value to notification (Priority: P1)

A user (or a connected service) performs an action; the portal records a domain event, writes
history, and interested systems (statistics, gamification, community, achievements,
marketplace, projects, automations, AI) react, ultimately producing notifications that invite
the next action.

**Why this priority**: The event/history loop is the transversal backbone that makes
statistics, gamification, community, automations, and AI coherent rather than siloed.

**Independent Test**: Trigger a representative action (e.g., finishing a media item); verify a
domain event is recorded with real occurrence time, history is written with provenance, at
least one consumer (e.g., a statistic or XP award) reacts deterministically, and a
notification is produced according to the user's preferences.

**Acceptance Scenarios**:

1. **Given** a recordable action, **When** it occurs, **Then** a domain event is recorded with
   `occurred_at` (real occurrence) distinct from `received_at` (portal receipt).
2. **Given** duplicate delivery of the same event, **When** consumers process it, **Then** the
   outcome is identical to single delivery (idempotent where duplicates are possible).
3. **Given** a consumer is temporarily unavailable, **When** it recovers, **Then** unrelated
   consumers' reactions are unaffected.

### User Story 4 - Search and AI in parallel (Priority: P1)

A user searches. Classic results appear immediately while the AI analyzes in parallel. If the
AI is unavailable, classic search still works; if classic search fails, the AI can still use
the sources it legitimately has access to.

**Why this priority**: Parallel, non-blocking search and AI is a locked decision and a core UX
promise; coupling them would make each a single point of failure for the other.

**Independent Test**: Issue a query; confirm classic results render without waiting for AI;
disable AI and confirm search still returns results; then confirm AI, when available, enriches
in parallel.

**Acceptance Scenarios**:

1. **Given** a query, **When** submitted, **Then** classic results are presented without
   waiting for the AI response.
2. **Given** the AI is unavailable, **When** the user searches, **Then** classic search remains
   fully usable.
3. **Given** the AI is available, **When** results return, **Then** AI analysis is presented in
   parallel without blocking classic results.

### User Story 5 - Onboarding to a working starter environment (Priority: P2)

A new user is guided through welcome, authentication, profile, service connection, interests,
notification and privacy choices, and arrives at an automatically configured starter dashboard
and discovery — a usable environment without manual setup.

**Why this priority**: First-run determines whether the portal feels like one environment;
the starter dashboard is explicitly required by the Blueprint.

**Independent Test**: Complete first connection as a brand-new account; verify a starter
dashboard is auto-configured within policy and discovery surfaces are populated, with no
dead-ends.

**Acceptance Scenarios**:

1. **Given** a new account, **When** onboarding completes, **Then** a starter dashboard is
   automatically configured within administrative policy.
2. **Given** onboarding steps, **When** the user sets notification/privacy preferences,
   **Then** those preferences are honored immediately afterward.

### User Story 6 - Virtual economy, Marketplace, and community participation (Priority: P2)

A user earns XP, Contribution, and Coins through activity; spends Coins in the Marketplace
(e.g., unlocking a plugin that activates immediately), participates in community projects by
voting (free) and optionally funding (Coins), where funding does not guarantee implementation.

**Why this priority**: The economy/marketplace/community cluster is a major product surface and
convergence point, governed by strict locked rules (virtual-only coins, immediate activation,
vote/fund independence).

**Independent Test**: As an active account, earn Coins via a tracked action, purchase a
permanent Marketplace product, confirm it is not purchasable twice and (if a plugin) activates
immediately; separately, cast a free vote and add optional funding to a project and confirm
they are independent.

**Acceptance Scenarios**:

1. **Given** sufficient Coins, **When** a user purchases a permanent product, **Then** a
   traceable transaction is recorded and the product cannot be purchased again unless explicitly
   repeatable.
2. **Given** a Marketplace plugin purchase, **When** no explicit configuration is required,
   **Then** the plugin activates immediately.
3. **Given** any active account, **When** they vote on a community project, **Then** the vote is
   accepted with no minimum level, and funding (if any) is recorded independently of the vote.

### User Story 7 - Support: tickets, incidents, Wiki, AI diagnosis (Priority: P2)

A user encountering a problem sees known incidents and Wiki guidance, optionally gets an AI
diagnosis that prefills a ticket for their review before submission, and tracks the ticket to
resolution.

**Why this priority**: Support closes the loop on reliability and reduces duplicate effort;
the AI-diagnosis-then-human-review flow is explicitly specified.

**Independent Test**: From a service-problem journey, confirm known incidents/maintenance are
surfaced, Wiki is reachable, AI can prefill a ticket, and the user reviews before submitting.

**Acceptance Scenarios**:

1. **Given** a systemic problem exists as an incident, **When** a user starts a related ticket,
   **Then** the known incident is surfaced to reduce duplicate tickets.
2. **Given** AI diagnosis is available, **When** it prefills a ticket, **Then** the user reviews
   and confirms before submission.

### User Story 8 - Privacy, data export, and account deletion lifecycle (Priority: P2)

A user inspects their data, controls visibility (Public, Community, Leaderboard-only,
Private), exports their data, and can delete their account as a lifecycle that anonymizes or
removes personal data while preserving necessary aggregate/historical integrity and destroying
remaining Coins at final deletion.

**Why this priority**: Privacy-by-design and a correct deletion lifecycle are locked rules with
legal and trust significance.

**Independent Test**: As a user, change a visibility preference and confirm enforcement; export
data and confirm completeness; initiate deletion and confirm the lifecycle (personal data
removed/anonymized, aggregates preserved where non-identifying, remaining Coins destroyed).

**Acceptance Scenarios**:

1. **Given** a visibility preference, **When** set by the user, **Then** it is enforced within
   administrative policy and independently of functional permissions.
2. **Given** an admin visibility override is applied then removed, **When** it is removed,
   **Then** the user's original preference is restored.
3. **Given** final account deletion, **When** it completes, **Then** personal data is
   deleted/anonymized, remaining Coins are destroyed, and historical transaction integrity is
   preserved.

### User Story 9 - Administration of a single-admin portal (Priority: P2)

The single Admin account configures users, modules/plugins, connectors/services, content,
support, gamification, Marketplace, statistics, notifications, AI, appearance, security, audit,
automations, and portal health — with sensitive actions confirmed and audited, and no temporary
role delegation.

**Why this priority**: Administration governs the whole product and enforces the locked
"exactly one Admin, no delegation" rule.

**Independent Test**: As the Admin, exercise one action in each administration domain; confirm
sensitive actions require confirmation and produce audit entries; confirm the system permits
exactly one Admin and rejects temporary delegation.

**Acceptance Scenarios**:

1. **Given** the portal, **When** roles are assigned, **Then** exactly one account holds the
   Admin role and temporary delegation is not possible.
2. **Given** a sensitive admin action, **When** performed, **Then** it is confirmed where
   appropriate and recorded in the audit trail with actor, action, timestamp, context, and
   result where relevant.

### User Story 10 - Personalization and theming without changing functional truth (Priority: P3)

A user personalizes their dashboard (add/remove/reorder/resize/configure widgets within
policy) and selects themes that profoundly change appearance, while functional state, business
rules, permissions, source-of-truth, and accessibility preferences remain unchanged.

**Why this priority**: Personalization and theming are differentiators, but subordinate to the
functional/presentation separation; they must never alter meaning.

**Independent Test**: Reorder and configure widgets within policy; switch themes; confirm
functional states keep identical meaning and accessibility preferences stay in effect.

**Acceptance Scenarios**:

1. **Given** dashboard personalization within policy, **When** a widget is mandatory or locked
   by admin policy, **Then** the user cannot remove or override it.
2. **Given** a theme change, **When** applied, **Then** functional state meaning is unchanged
   and accessibility preferences remain effective.

### User Story 11 - Automations reacting to events and conditions (Priority: P3)

A user or admin defines WHEN to IF to THEN automations that react to domain events and/or
conditions and perform authorized actions, with execution history and loop protection, bounded
to the authoring user's permissions.

**Why this priority**: Automations add significant power but are explicitly "not a full n8n
clone" and must obey permissions and determinism.

**Independent Test**: Define an automation triggered by a domain event with a condition and an
authorized action; trigger it; confirm deterministic execution, an execution history entry, and
that it cannot perform actions the author is not permitted to perform.

**Acceptance Scenarios**:

1. **Given** an automation whose action exceeds the author's permissions, **When** it would
   run, **Then** the unauthorized action is refused.
2. **Given** an automation that could trigger itself, **When** it runs, **Then** loop protection
   prevents runaway execution and an execution history entry is recorded.

### Edge Cases

- **Overlapping campaigns**: When multiple campaigns overlap, modifiers combine via
  deterministic configured rules; duplicate rewards are prevented and anti-farming limits apply.
- **Late/duplicate sync**: When a service delivers an event late or twice, `occurred_at` is used
  for ordering/attribution and consumers remain idempotent; a full resync must not blindly
  destroy native portal data.
- **Service disconnected vs outage**: Disconnection stops live access/sync but does not erase
  history; an outage does not erase existing data; sync state and service health remain
  distinct.
- **Plugin disabled/failed**: Disabling a plugin does not delete its data; a plugin failure must
  not break unrelated portal functions.
- **Archived Marketplace product**: Existing owners keep access; the product is no longer newly
  purchasable.
- **Coins at deletion**: Remaining Coins are destroyed at final deletion; refunds are new
  transactions, never retroactive edits.
- **Admin visibility override**: Applying/removing an override never destroys the user's
  underlying preference.
- **Historical rule change**: Past rewards/transactions stay bound to the rule version in force
  when they occurred; new rules do not reinterpret historical data.
- **AI acting on sensitive operations**: AI-initiated sensitive actions require the same
  confirmation and authorization as human-initiated ones.
- **No-data / unauthorized surfaces**: Surfaces present distinguishable "no data" and
  "unauthorized" states rather than dead-ends or silent failures.

## Requirements *(mandatory)*

### Functional Requirements

#### Portal Core, Identity, Users, Roles, Permissions
- **FR-001**: The portal MUST provide a single coherent environment that is the primary entry
  point to the user's digital environment, not a collection of links.
- **FR-002**: The system MUST authenticate users and maintain user identity, profile, and
  preferences.
- **FR-003**: Authorization MUST be enforced server-side with default-deny; permissions MUST NOT
  be enforced only in the UI.
- **FR-004**: The system MUST support roles (at minimum User, Support, Moderator, Editor, Admin)
  mapped to permissions expressed as `domain.action.scope`.
- **FR-005**: The system MUST permit exactly one Admin account and MUST NOT allow temporary role
  delegation.
- **FR-006**: Plugins MUST be able to declare additional permissions that integrate with the
  same authorization model.
- **FR-007**: Sensitive operations (deletion, permission changes, significant refunds,
  economy-rule changes, destructive service/data actions) MUST be confirmed where appropriate and
  MUST be audited.

#### Modules, Plugins, Connectors, Services, Capabilities, Extensibility
- **FR-008**: The portal MUST organize functionality into Modules (at least Home, Media,
  Community, Statistics, Support, Marketplace, Services, News, Calendar, Administration).
- **FR-009**: Modules MUST depend on Capabilities (functional contracts), not on concrete
  services, whenever a capability abstraction is possible.
- **FR-010**: The system MUST represent Connectors (external integrations), Services (concrete
  instances), and Capabilities (functional abilities) as distinct concepts.
- **FR-011**: Adding a new service MUST be primarily additive and MUST NOT require rewriting
  existing modules.
- **FR-012**: Plugins MUST be able to add pages, add features, enrich existing pages, enrich
  existing objects, add widgets, add statistics, add settings, declare permissions, and
  consume/produce domain events.
- **FR-013**: Disabling a plugin MUST NOT automatically delete its data; a plugin failure MUST
  NOT break unrelated portal functions.
- **FR-014**: The Core and every Module MUST remain functional when optional plugins are absent.
- **FR-015**: Extension activation/update MUST check portal version, dependencies, capabilities,
  permissions, and configuration for compatibility before enabling.
- **FR-016**: The extension lifecycle MUST support the states Available, Installed, Configured,
  Enabled, Updated, Disabled, Archived/Removed; Marketplace items follow
  Purchased, Unlocked, Enabled-immediately-by-default (unless explicit configuration required).

#### Events & History
- **FR-017**: The system MUST record domain events describing facts that happened, decoupling
  producers from consumers.
- **FR-018**: Each domain event MUST carry at least an identifier, type, real occurrence time
  (`occurred_at`), portal receipt time (`received_at`), source, actor/context,
  object/reference, metadata, and version.
- **FR-019**: Event consumers MUST be idempotent wherever duplicate delivery is possible.
- **FR-020**: The system MUST persist history with the provenance and context required by
  consuming features; historized data MUST NOT be treated as automatically public.

#### Search & Command Palette
- **FR-021**: The portal MUST provide global search that returns classic results immediately,
  without waiting for AI.
- **FR-022**: Search and AI MUST run in parallel and independently; failure of one MUST NOT block
  the other.
- **FR-023**: The portal MUST provide a Command Palette for fast navigation and actions, bounded
  by the user's permissions.

#### Dashboard & Widgets
- **FR-024**: The Home dashboard MUST present widgets that load independently so a slow or failing
  widget does not block others.
- **FR-025**: The portal MUST provide a "Since Last Login" summary of relevant changes.
- **FR-026**: Users MUST be able to add, remove, reorder, resize, and configure widgets within
  administrative policy.
- **FR-027**: Admin policy MUST be able to mark widgets as free, default, mandatory, locked,
  disabled, or conditional, and the system MUST enforce those policies over user personalization.
- **FR-028**: Onboarding MUST automatically configure a starter dashboard within policy.

#### Notifications, News, Wiki, Calendar
- **FR-029**: The system MUST treat notification, alert, news, and email as distinct concepts,
  deliverable via channels including portal, email, and sound (with push as a future channel).
- **FR-030**: Users MUST be able to control notification categories where policy allows.
- **FR-031**: The portal MUST provide editorial News with featured items, scheduled publication,
  and discovery.
- **FR-032**: The portal MUST provide a Wiki for knowledge/help content, editable per permissions.
- **FR-033**: The portal MUST provide a unified Calendar including event details and a
  maintenance calendar.

#### Community
- **FR-034**: The portal MUST provide Community features: Members, Profile, Activity,
  Leaderboards, Quests, Daily objectives, Achievements, and Community Projects.
- **FR-035**: The portal MUST NOT include a core friends/followers/direct-message/chat system.
- **FR-036**: Every active account MUST be able to vote on community projects with no minimum
  level; voting is free.
- **FR-037**: Funding MUST be independent from voting; funding MUST NOT guarantee implementation;
  reserved funds MUST be refunded or consumed according to the project's published rules.

#### Gamification (XP, Contribution, Coins, Achievements, Quests, Campaigns)
- **FR-038**: The system MUST track exactly three separate values: XP (progression),
  Contribution (community value), and Coins (internal currency); Levels are progression tiers,
  not a fourth currency.
- **FR-039**: A reward engine MUST grant XP/Contribution/Coins/Achievements deterministically and
  traceably; manual rewards MUST be marked and audited.
- **FR-040**: Historical rewards MUST remain bound to the rule/version in force when granted;
  rules MUST be versionable where changes could affect interpretation of historical data.
- **FR-041**: Anti-abuse/anti-farming limits MUST apply, and duplicate rewards MUST be prevented.
- **FR-042**: Campaigns MUST support dates, recurrence, multipliers, achievements, quests,
  notifications, themes, and email behavior; multiple campaigns MAY overlap and MUST combine via
  deterministic configured conflict-resolution rules.

#### Internal Economy (Coins)
- **FR-043**: Coins MUST be strictly internal and virtual; the current product MUST NOT allow
  real-money coin purchases.
- **FR-044**: Every Coin movement MUST be recorded as a traceable transaction; balances MUST
  normally not become negative; any exception MUST be an explicit, audited manual correction.
- **FR-045**: Refunds MUST be represented as new transactions, never as retroactive edits.
- **FR-046**: On final account deletion, remaining Coins MUST be destroyed.

#### Marketplace
- **FR-047**: The Marketplace MUST offer products that may be plugins, widgets, statistics,
  themes, effects, badges/titles, quotas, features, or community projects.
- **FR-048**: Already-owned permanent products MUST NOT be purchasable twice unless explicitly
  repeatable; archived products MUST remain accessible to existing owners.
- **FR-049**: Request quota MAY be sold for Coins, but paid request processing priority MUST NOT
  exist.
- **FR-050**: Marketplace plugin purchases MUST activate immediately unless explicit configuration
  is required.

#### Support (Tickets, Incidents, Feedback, Wiki, AI diagnosis)
- **FR-051**: The portal MUST support Tickets (individual issues) and Incidents (broad/systemic
  problems) as distinct concepts.
- **FR-052**: Known incidents MUST be surfaced to reduce duplicate tickets.
- **FR-053**: Tickets MUST support types, workflows, and assignment.
- **FR-054**: AI MAY diagnose and prefill a ticket, but the user MUST review before submission.
- **FR-055**: The portal MUST provide Feedback and contextual help.
- **FR-056**: The portal MUST support Maintenance (scheduled/started/ended) surfaced on the
  calendar and relevant service surfaces.

#### Statistics
- **FR-057**: The portal MUST provide a statistics registry with visualization and filters.
- **FR-058**: The portal MUST support unlockable statistics and cross-service statistics derived
  from history/events.

#### Services & Supervision
- **FR-059**: The portal MUST support connector registry, service registration, auto-detection
  where possible, service configuration, service health, and infrastructure monitoring (e.g.,
  uptime, errors, CPU, RAM, disk, temperature, network, GPU, transcoding/load) according to
  permissions.
- **FR-060**: The portal MUST expose sync status and support manual sync; sync state and service
  health MUST be distinct.
- **FR-061**: External services MUST remain the source of truth for their native data; the portal
  MUST store only the representations/history its features require.

#### AI
- **FR-062**: The AI MUST operate under the current user's effective permissions and MUST NEVER
  bypass authorization.
- **FR-063**: The AI MAY understand, search, explain, recommend, navigate, and perform authorized
  actions; sensitive AI actions MUST obey the same authorization and confirmation rules as human
  actions.
- **FR-064**: AI responses MUST allow distinguishing real data, historical information, and
  interpretation/inference.
- **FR-065**: AI failure MUST NOT break classic (non-AI) functions; the system MUST support a
  provider abstraction so AI capability is not bound to a single concrete provider.

#### Automations
- **FR-066**: The portal MUST support WHEN/IF/THEN automations reacting to domain events
  and/or conditions and performing actions; it is explicitly not a full general-purpose workflow
  engine.
- **FR-067**: Automations MUST execute within the authoring user's permissions and MUST record
  execution history; loop protection MUST prevent runaway execution.

#### Administration
- **FR-068**: Administration MUST cover users, modules/plugins, connectors/services, content,
  support, gamification, Marketplace, statistics, notifications, AI, appearance, security, audit,
  automations, and portal health.
- **FR-069**: The Admin dashboard MUST surface portal health and the audit trail.

#### Onboarding & Personalization
- **FR-070**: Onboarding MUST guide welcome, authentication, profile, services, interests,
  notifications, privacy, starter dashboard, and discovery, with no dead-ends.
- **FR-071**: Personalization MUST be bounded by security, privacy, and business rules.

#### Themes & Accessibility
- **FR-072**: Themes MUST be able to change presentation (colors, typography, icons, backgrounds,
  textures, borders, shadows, density, animations, transitions, notification presentation, sounds)
  but MUST NOT change permissions, security, business rules, source-of-truth, or actual service
  state.
- **FR-073**: Accessibility MUST be transversal: features MUST remain usable with keyboard, touch,
  varying screen sizes, reduced motion, disabled sound, and contrast/legibility needs; mobile MUST
  remain functionally complete.
- **FR-074**: Accessibility preferences MUST take precedence over purely visual effects, and no
  visual personalization MUST render critical information inaccessible.

#### Privacy, Data Export, Account Deletion
- **FR-075**: Visibility MUST support Public, Community, Leaderboard-only, and Private; user
  preference and admin policy MUST be separate.
- **FR-076**: An admin visibility override MUST preserve the user's underlying preference and
  restore it when the override is removed.
- **FR-077**: Users MUST be able to inspect and export their data.
- **FR-078**: Account deletion MUST be a lifecycle: personal data deleted/anonymized at final
  deletion, aggregate data retained only when non-identifying and necessary, and historical
  transaction integrity preserved.

#### Synchronization
- **FR-079**: Synchronization MUST be idempotent where needed; event occurrence time MUST NOT be
  treated as sync receipt time.
- **FR-080**: Conflicting sources MUST follow configured source-of-truth rules or preserve
  provenance; a full resync MUST NOT blindly destroy native portal data; an outage MUST NOT erase
  existing data.

#### Observability
- **FR-081**: Important operations MUST be observable, and the portal MUST be able to diagnose its
  own problems and those of connected services.
- **FR-082**: Errors MUST be explainable and actionable rather than merely masking failure.

#### Functional States (cross-cutting)
- **FR-083**: Surfaces MUST be able to distinguish the functional states loading, available,
  partial, stale, error, unavailable, maintenance, unauthorized, no data, and syncing where
  relevant, and stale data MUST be identifiable as such.

#### Configuration Hierarchy (cross-cutting)
- **FR-084**: Configuration MUST follow the precedence Global, Module, Plugin, User; admin
  policies MAY impose constraints; user preferences MUST be retained where still permitted;
  defaults MUST yield a usable experience without excessive configuration.

### Key Entities

- **User**: An identity with roles, permissions, preferences, visibility policy, progression
  (XP/Contribution/Level), activity, transactions, purchases, votes, and funding.
- **Role / Permission**: Named role mapped to `domain.action.scope` permissions; exactly one
  Admin.
- **Preference / VisibilityPolicy**: User choices and effective visibility, separate from
  permissions; supports admin overrides that preserve the underlying preference.
- **Module**: A major portal area.
- **Plugin**: Optional functionality with its own permissions, capabilities, pages, widgets,
  events, configuration, and data.
- **Connector / Service / Capability**: External integration / concrete instance / functional
  contract consumed by modules.
- **Domain Event**: A recorded fact (type, `occurred_at`, `received_at`, source, actor/context,
  object/reference, metadata, version).
- **HistoryEntry**: Persisted portal history with provenance and context.
- **AuditEntry**: Record of a sensitive action (actor, action, timestamp, context, result).
- **Notification**: A portal communication; distinct from alert, news, and email.
- **NewsArticle / WikiPage / CalendarEvent**: Editorial content / knowledge content / calendar
  item (including maintenance).
- **SyncJob**: A synchronization run with state distinct from service health.
- **Incident / Maintenance**: Systemic problem / scheduled or ongoing maintenance.
- **Ticket / Feedback**: Individual support issue / user feedback.
- **MediaObject**: A unified-catalog item with external identities, sessions, statistics,
  achievements, and events.
- **Statistic**: A registered, visualizable, filterable metric; may be unlockable or
  cross-service.
- **Achievement / Quest / Level / RewardRule**: Milestone / challenge / progression tier /
  versionable reward rule.
- **EconomyTransaction**: A traceable Coin movement; refunds are new transactions.
- **MarketplaceProduct / Purchase**: Offered product (plugin/widget/stat/theme/effect/badge/
  quota/feature/project) / ownership record.
- **CommunityProject / Vote / Funding**: Proposed evolution / free vote / independent Coin
  funding with published fund rules.
- **Campaign**: A time-bound themed operation with dates, recurrence, multipliers, achievements,
  quests, notifications, themes, and email behavior; deterministic overlap resolution.
- **Theme**: A presentation layer that cannot change functional truth.
- **Automation / AutomationExecution**: WHEN/IF/THEN reaction bounded by author permissions /
  its execution record with loop protection.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A returning user can see what changed since last login and reach any enabled module
  in no more than two interactions from Home.
- **SC-002**: When any single external service is unavailable, 100% of functions that do not
  depend on that service remain usable.
- **SC-003**: Classic search returns results without waiting for AI in 100% of searches, and
  search remains usable in 100% of cases where the AI is unavailable.
- **SC-004**: Disconnecting a service or experiencing an outage results in 0 cases of automatic
  erasure of previously historized portal data.
- **SC-005**: 100% of sensitive administrative actions produce an audit entry containing actor,
  action, timestamp, context, and result where relevant.
- **SC-006**: The portal permits exactly one Admin account and rejects 100% of attempts to create
  a second Admin or to delegate the role temporarily.
- **SC-007**: 100% of Coin movements are represented as traceable transactions; 0 refunds are
  implemented as retroactive edits; 100% of final account deletions destroy remaining Coins.
- **SC-008**: A permanent Marketplace product cannot be purchased twice (unless repeatable) in
  100% of attempts, and non-configuration plugin purchases activate immediately.
- **SC-009**: Every active account can vote with no minimum level, and voting and funding are
  recorded independently in 100% of cases.
- **SC-010**: Switching themes changes 0 functional-state meanings and keeps 100% of accessibility
  preferences in effect.
- **SC-011**: 100% of acceptance scenarios in this specification are expressible as verifiable
  tests before any detailed feature is implemented.
- **SC-012**: Duplicate delivery of a domain event produces an identical outcome to single
  delivery in 100% of idempotent consumers.

## Assumptions

- The portal is independent of any specific private deployment or homelab identity; it is a
  general product, not tied to one operator's infrastructure.
- "Users" are primarily a personal/community-oriented audience; this is not a large-scale public
  SaaS, so performance targets follow standard interactive-web expectations unless a detailed spec
  states otherwise.
- The single-Admin model implies all other accounts are non-Admin; support/moderation/editing are
  expressed through the Support, Moderator, and Editor roles rather than additional Admins.
- "Immediately" for plugin activation means without a manual enable step, subject only to any
  explicitly required configuration.
- Push notifications are a future channel; the current scope requires portal, email, and sound
  channels.
- Where the Blueprint lists capabilities of a module without exhaustive rules, detailed feature
  specs will refine them without contradicting this global specification.

## Open Questions & Flagged Ambiguities

These are genuine ambiguities in the current product documentation. They are flagged, not
resolved, per the instruction not to invent rules. They should be addressed in `/speckit.clarify`
or by a product decision before dependent detailed specs are finalized.

- **OQ-1 (Terminology — Event vs Campaign) — ✅ RESOLVED (CD-009)**: canonical vocabulary fixed —
  **Domain Event** (recorded fact), **Campaign** (time-bound themed operation), **Automation**
  (configurable reaction) — distinct and applied consistently across all specs. See
  `decisions/CANONICAL_DECISIONS.md` (CD-009). No longer open.
- **OQ-2 (Automation triggers)**: The documentation describes WHEN/IF/THEN over "events/
  conditions" but does not state whether triggers may be purely time-/schedule-based or must
  originate from a domain event. Scope of triggers needs confirmation.
- **OQ-3 (Coin non-negativity exceptions)**: Coins "normally" cannot be negative. The precise set
  of permitted exceptions (e.g., audited manual corrections, reserved-funding mechanics) is not
  enumerated and needs confirmation.
- **OQ-4 (Idempotency key)**: Events must be idempotent "where needed," but the deduplication key
  and window are not specified at the product level. Confirm whether this is a product rule or
  deferred to detailed specs.
- **OQ-5 (Specification granularity)**: Confirm whether detailed specs will be authored per
  feature ID (e.g., CORE-001), per module, or per capability — this governs how this global spec
  is decomposed next.

## Dependencies

- Conforms to and depends on: `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`,
  `decisions/DECISIONS.md`, `architecture/FUNCTIONAL_ARCHITECTURE.md`,
  `architecture/EVENT_MODEL.md`, `architecture/PERMISSION_MODEL.md`,
  `architecture/DATA_MODEL.md`, `architecture/EXTENSIBILITY.md`, `features/FEATURE_CATALOG.md`,
  `ux/USER_JOURNEYS.md`, `ux/UX_PRINCIPLES.md`, `ux/DESIGN_SYSTEM.md`, `ux/THEMING.md`.
- Governed by: the project Constitution (`.specify/memory/constitution.md`, v1.0.0).
- All subsequent detailed feature specifications depend on this document as their superior
  reference.
