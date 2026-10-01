# Feature Specification: Notifications & Communication

**Feature Branch**: `010-notifications`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Detailed functional specification of the Notifications & Communication system."

## Role of This Document

This is a **detailed feature specification** for Notifications & Communication — the system that turns
events, rules, and automations into user-facing communications across channels. It conforms to and
refines the superior reference specification (`specs/001-portal-global-spec/spec.md`) and composes with
Roles & Permissions (`specs/003-roles-permissions/spec.md`), the Portal Core shell
(`specs/004-portal-core-shell/spec.md`), Events & History (`specs/007-events-history/spec.md`), and the
Dashboard (`specs/009-dashboard-widgets/spec.md`), under the project Constitution
(`.specify/memory/constitution.md`, v1.0.0). It draws on `product/PRODUCT_BLUEPRINT.md`,
`product/BUSINESS_RULES.md`, `ux/UX_PRINCIPLES.md`, `ux/DESIGN_SYSTEM.md`, and `ux/THEMING.md`.

Scope boundary: this spec owns the **notification/communication mechanism** — the four distinct
concepts (Notification, Alert, News, Email), the notification center, priorities/categories, user
preferences, delivery channels (portal, email, sound; push as future), presentation (position,
duration, styles, animations) with accessibility, and **system-generated notifications**. Configurable
notification rules are **not** a separate engine owned here: they are expressed and executed through the
**single generic WHEN→IF→THEN engine owned by Automations (spec 019 / CD-010)**, with "produce a
communication" as an Automation action. This spec does **not** own News editorial authoring (owned by
the News module), the Automations engine (owned by spec 019), the event store (owned by Events &
History), or the authorization/privacy engines — it composes with them. It chooses no technology and
contains no implementation detail.

### Strict Conceptual Distinctions (normative)

These four concepts are **distinct** and MUST never be conflated in data, UI, or logic:

- **Notification**: a targeted, per-user portal communication about something relevant to that user
  (e.g., "your download finished"). Lives in the notification center; has priority/category; delivery
  governed by user preferences within policy.
- **Alert**: a higher-urgency signal requiring attention now (e.g., "service critical",
  "maintenance starting"). May bypass some muting per policy; visually/behaviorally distinct from an
  ordinary Notification; still permission/privacy bound.
- **News**: editorial, broadcast content authored for an audience (owned by the News module). It is not
  per-user state and is not the same as a Notification, though a News item MAY trigger a Notification.
- **Email**: an out-of-portal delivery channel carrying a Notification/Alert/News digest to the user's
  email, governed by separate email preferences and policy.

**Terminology**: the WHEN/IF/THEN model below is the generic Automations engine (spec 019); here WHEN =
trigger (event/schedule/condition), IF = condition filter, THEN = a communication action. Notifications
defines **how communications are produced/delivered** as Automation actions; it does not define a second
engine. Domain Event = a recorded fact; `occurred_at` = real occurrence time.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Notification center with priorities and categories (Priority: P1)

A user opens the notification center and sees their notifications organized by category and priority,
can read/mark/dismiss them, and the unread state is reflected in the shell.

**Why this priority**: The notification center is the primary surface where per-user communications
converge; without it, notifications have nowhere to live.

**Independent Test**: Generate notifications of different categories/priorities; open the center;
confirm they appear organized by category/priority, can be marked read/dismissed, and the shell's
unread indicator reflects the state.

**Acceptance Scenarios**:

1. **Given** a user has notifications, **When** they open the notification center, **Then** the
   notifications appear with their category and priority.
2. **Given** an unread notification, **When** it arrives, **Then** the shell's notification surface
   reflects the unread state; **When** read/dismissed, **Then** the state updates.
3. **Given** notifications of different priorities, **When** displayed, **Then** higher-priority items
   are distinguishable and ordered appropriately.

### User Story 2 - The four distinct concepts behave distinctly (Priority: P1)

Notification, Alert, News, and Email are handled as separate concepts: an Alert is more urgent than an
ordinary Notification, News is editorial broadcast content, and Email is a separate delivery channel —
each with its own rules, never conflated.

**Why this priority**: "Notification, alert, news and email are distinct" is a locked product decision;
conflating them would break preferences, urgency handling, and privacy.

**Independent Test**: Produce one of each; confirm an Alert is treated with higher urgency than a
Notification, News appears as editorial (not per-user state), and Email is delivered via the email
channel governed by email preferences — with no concept collapsed into another.

**Acceptance Scenarios**:

1. **Given** a Notification and an Alert for the same user, **When** delivered, **Then** the Alert is
   treated as higher urgency and is visually/behaviorally distinct.
2. **Given** a News item, **When** published, **Then** it is editorial broadcast content and is not
   stored as a per-user Notification (though it MAY trigger a Notification).
3. **Given** an Email delivery, **When** sent, **Then** it is governed by email preferences/policy,
   separate from in-portal notification preferences.

### User Story 3 - User preferences by category and channel (Priority: P1)

A user controls, per category and per channel (portal, email, sound), whether and how they receive
communications, within administrative policy; preferences are honored immediately.

**Why this priority**: "User controls categories where policy allows" is explicit; preferences are the
user-level tier of the configuration hierarchy.

**Independent Test**: Toggle a category off for email but on for portal; set sound off; confirm each
preference is honored on the next matching communication, and that policy-forced categories cannot be
disabled.

**Acceptance Scenarios**:

1. **Given** a category the user may control, **When** they disable it for a channel, **Then** matching
   communications are not delivered on that channel while still honored on enabled channels.
2. **Given** a policy-mandated category (e.g., critical Alerts), **When** the user attempts to disable
   it, **Then** it is refused (policy precedence) while the user's underlying preference is retained.
3. **Given** a preference change, **When** saved, **Then** it is honored on the next matching
   communication and a `user.preferences_updated`-type record is produced.

### User Story 4 - Communications produced via the Automations WHEN → IF → THEN engine (Priority: P1)

Configurable communications are generated through the **single generic WHEN→IF→THEN engine owned by
Automations (spec 019 / CD-010)**: WHEN a trigger fires (a domain event, a schedule, or an automation),
IF the conditions hold (audience, preference, policy, dedup), THEN one or more communications are
produced on the appropriate channels as an Automation action. Notifications does not define a second
engine.

**Why this priority**: Tying events/automations/admin rules to user communications is core; reusing the
single Automations engine (rather than a competing one) is required by CD-010.

**Independent Test**: Define a rule triggered by a domain event with a condition and a notification
action; fire the event; confirm the condition is evaluated and, when met, the communication is produced
on the right channels for the right audience, respecting preferences and permissions.

**Acceptance Scenarios**:

1. **Given** a rule WHEN a domain event occurs IF conditions hold THEN notify, **When** the event
   fires and conditions hold, **Then** the communication(s) are produced for the permitted audience on
   the enabled channels.
2. **Given** the same rule, **When** conditions do not hold, **Then** no communication is produced.
3. **Given** a rule sourced from an admin rule or an automation, **When** it fires, **Then** it uses
   the same engine and the same preference/permission/dedup rules as event-sourced rules.
4. **Given** duplicate or repeated triggers, **When** evaluated, **Then** the engine is idempotent and
   does not produce duplicate communications for the same logical occurrence.

### User Story 5 - Scheduled maintenance notifications (J-1 / H-1 / start) (Priority: P1)

For a planned maintenance, the system emits a day-before (J-1) notification, an imminent (H-1)
notification, and an immediate notification when maintenance starts — each via the rule engine, scoped
to the permitted audience and preferences.

**Why this priority**: This is the explicit worked example and a common high-value communication
pattern combining schedule-based and event-based triggers.

**Independent Test**: Schedule a maintenance; confirm a J-1 notification is produced one day before, an
H-1 notification one hour before, and an immediate notification when `maintenance.started` fires — each
respecting audience, preferences, and dedup.

**Acceptance Scenarios**:

1. **Given** a maintenance scheduled for tomorrow, **When** the J-1 point is reached, **Then** a
   day-before notification is produced for the permitted audience.
2. **Given** the maintenance is imminent, **When** the H-1 point is reached, **Then** an hour-before
   notification is produced.
3. **Given** the maintenance starts (`maintenance.started`), **When** the event fires, **Then** an
   immediate notification/alert is produced.
4. **Given** all three, **When** produced, **Then** they are not duplicated for the same user and
   respect each user's preferences and permissions.

### User Story 6 - Automatic, admin-rule, event, and automation sources (Priority: P2)

Communications can be automatic (system-generated), generated by administrative rules, derived from
domain events, or produced by automations — all converging through the same engine and the same
preference/permission/audit rules.

**Why this priority**: The four sources are explicitly listed; unifying them prevents parallel,
inconsistent notification mechanisms (Constitution principle XX).

**Independent Test**: Trigger a communication from each source; confirm all pass through the same engine
with consistent preference/permission handling and consistent recording.

**Acceptance Scenarios**:

1. **Given** an automatic system communication, **When** produced, **Then** it follows the same
   preference/permission/dedup rules as all others.
2. **Given** an admin-rule communication, **When** produced, **Then** it is permission-bounded and
   audited where it constitutes a sensitive admin action.
3. **Given** an automation-produced communication, **When** produced, **Then** it is bounded by the
   automation author's permissions and recorded in automation execution history.

### User Story 7 - Presentation, accessibility, reduced motion, sound off (Priority: P1)

Notifications present with configurable position, duration, style, and animation, but accessibility
preferences (reduced motion, sound off) and functional meaning always take precedence; presentation is
independent of the communication's functional meaning/urgency.

**Why this priority**: Accessibility is transversal and locked; "themes/presentation never change
functional truth" applies to notifications' urgency and meaning.

**Independent Test**: Set reduced motion and sound off; produce notifications/alerts; confirm no
animation/sound plays while the communication and its urgency are still fully conveyed; switch themes
and confirm only appearance changes.

**Acceptance Scenarios**:

1. **Given** reduced-motion preference, **When** a notification appears, **Then** it is shown without
   motion while still conveying its content and urgency.
2. **Given** sound-off preference, **When** a notification/alert arrives, **Then** no sound plays while
   the communication is still delivered visually.
3. **Given** a theme change, **When** notifications render, **Then** only appearance (position,
   duration, style, sound where enabled) changes; the functional meaning/urgency is unchanged.
4. **Given** any presentation settings, **When** applied, **Then** critical information and urgency
   remain accessible (presentation never hides functional truth).

### User Story 8 - Email and multi-channel delivery (Priority: P2)

A communication may be delivered across channels (portal, email, sound; push in future) per the user's
per-channel preferences and policy; email delivery is a distinct channel with its own formatting and
preferences.

**Why this priority**: Email and multi-channel delivery are explicit; channel independence is needed so
disabling one channel does not disable the communication everywhere.

**Independent Test**: Enable portal+email for a category, disable sound; produce a matching
communication; confirm it appears in the portal and is emailed but makes no sound, and that email
formatting respects the email channel.

**Acceptance Scenarios**:

1. **Given** per-channel preferences, **When** a communication is produced, **Then** it is delivered
   only on the channels enabled for its category (within policy).
2. **Given** email is enabled, **When** a communication is emailed, **Then** it uses email-appropriate
   formatting and respects email preferences/policy, distinct from in-portal presentation.
3. **Given** a channel is unavailable (e.g., email delivery fails), **When** delivery is attempted,
   **Then** failure on one channel does not prevent delivery on other enabled channels, and the failure
   is observable.

### Edge Cases

- **Duplicate triggers**: The engine deduplicates so one logical occurrence does not produce multiple
  identical communications to the same user (e.g., a redelivered event, or J-1 evaluated twice).
- **Preference vs policy conflict**: Policy-mandated categories (e.g., critical Alerts) cannot be
  disabled; policy wins while the user's underlying preference is retained for restoration.
- **Alert bypasses muting**: A critical Alert may bypass certain user mutes per policy, but never
  bypasses permissions or privacy.
- **Reduced motion / sound off**: Suppress animation/sound only; the communication and its urgency are
  still delivered; accessibility preference takes precedence over presentation settings.
- **Channel failure**: Failure to deliver on one channel (e.g., email) does not block other channels;
  the failure is observable and does not break unrelated functions.
- **Private data in communications**: A communication never surfaces data the recipient is not
  permitted to see and never exposes another user's Private data; no secrets in payloads.
- **News vs Notification**: A News publication may trigger Notifications, but News itself is not stored
  as per-user notification state.
- **Recipient loses permission before delivery**: If the recipient no longer may see the subject, the
  communication is withheld/redacted on next evaluation.
- **Late schedule evaluation**: If J-1/H-1 points are reached late (e.g., system was down), the engine
  resolves sensibly (fires once if still relevant, or skips if the window has passed) without
  duplicate or nonsensical notifications. (See OQ-46.)
- **Maintenance cancelled after J-1 sent**: A follow-up/cancellation communication is produced rather
  than leaving a stale expectation. (See OQ-47.)
- **High volume / storms**: The engine avoids flooding a user (batching/throttling within policy) while
  never dropping critical Alerts silently.
- **Account deletion**: Pending/undelivered communications and notification history follow the privacy/
  deletion lifecycle (anonymized/removed as applicable).

## Requirements *(mandatory)*

### Functional Requirements

#### Distinct Concepts
- **FR-001**: The system MUST model Notification, Alert, News, and Email as distinct concepts and MUST
  NEVER conflate them in data, UI, or logic.
- **FR-002**: An Alert MUST be treated with higher urgency than an ordinary Notification and MUST be
  visually/behaviorally distinct; an Alert MAY bypass certain user mutes per policy but MUST NOT bypass
  permissions or privacy.
- **FR-003**: News MUST be editorial broadcast content (owned by the News module) and MUST NOT be
  stored as per-user Notification state, though a News item MAY trigger a Notification.
- **FR-004**: Email MUST be a distinct delivery channel governed by separate email preferences/policy.

#### Notification Center, Priorities, Categories
- **FR-005**: The system MUST provide a notification center listing a user's notifications with
  category and priority, supporting read/mark/dismiss, with unread state reflected in the shell.
- **FR-006**: Notifications MUST carry a priority and a category; higher-priority items MUST be
  distinguishable and ordered appropriately.
- **FR-007**: Categories MUST be defined such that users can control them where policy allows.

#### User Preferences & Channels
- **FR-008**: Users MUST be able to control, per category and per channel (portal, email, sound; push
  in future), whether/how they receive communications, within administrative policy.
- **FR-009**: Preference changes MUST be honored on the next matching communication and MUST follow the
  configuration hierarchy (policy precedence with user preference retained for restoration).
- **FR-010**: Policy-mandated categories (e.g., critical Alerts) MUST NOT be user-disable-able; the
  attempt MUST be refused while retaining the underlying preference.
- **FR-011**: Disabling a category on one channel MUST NOT disable it on other enabled channels.

#### Communication Rules via the Automations Engine (spec 019 / CD-010)
- **FR-012**: Configurable communications MUST be produced through the single generic WHEN→IF→THEN engine
  owned by Automations (019) — WHEN a trigger (domain event, schedule, or automation), IF a condition
  filter (audience, preference, policy, dedup), THEN one or more communication actions on appropriate
  channels. Notifications MUST NOT provide a second generic engine.
- **FR-013**: Communications MUST be produced only when conditions hold, for the permitted audience, on
  the enabled channels (as the "produce communication" Automation action).
- **FR-014**: Communication production MUST be idempotent: duplicate or repeated triggers for the same
  logical occurrence MUST NOT produce duplicate communications (dedup per Events & History / CD-012).
- **FR-015**: Schedule-based triggers (e.g., J-1, H-1 relative to a scheduled time), event-based, and
  automation-based triggers are all handled by the Automations engine (019); Notifications consumes them.

#### Sources (automatic, admin rules, events, automations)
- **FR-016**: Communications MUST be producible from automatic/system sources, administrative rules,
  domain events, and automations — all converging through the same engine and the same preference/
  permission/dedup rules (no parallel mechanism).
- **FR-017**: Admin-rule communications MUST be permission-bounded and MUST be audited where they
  constitute a sensitive administrative action.
- **FR-018**: Automation-produced communications MUST be bounded by the automation author's permissions
  and MUST be recorded in automation execution history.
- **FR-019**: Event-sourced communications MUST consume domain events idempotently using `occurred_at`,
  consistent with Events & History.

#### Maintenance Worked Example
- **FR-020**: For a scheduled maintenance, the system MUST be able to produce a day-before (J-1)
  notification, an hour-before (H-1) notification, and an immediate notification/alert when
  `maintenance.started` fires — each for the permitted audience, respecting preferences and dedup.
- **FR-021**: If a scheduled maintenance is changed or cancelled after a J-1/H-1 notification was sent,
  the system MUST be able to produce a corrective/cancellation communication rather than leaving a
  stale expectation.

#### Presentation & Accessibility
- **FR-022**: Notifications MUST support configurable position, duration, style, and animation, and
  (where enabled) sound.
- **FR-023**: Accessibility preferences MUST take precedence: reduced motion MUST suppress animation and
  sound-off MUST suppress sound, while the communication and its urgency are still conveyed.
- **FR-024**: Presentation MUST be independent of functional meaning/urgency: a theme change MUST alter
  only appearance, never the urgency, meaning, or delivery of a communication.
- **FR-025**: No presentation setting MUST render a communication's critical information or urgency
  inaccessible.

#### Multi-Channel Delivery
- **FR-026**: A communication MUST be deliverable across multiple channels per the user's per-channel
  preferences and policy; email MUST use email-appropriate formatting distinct from in-portal
  presentation.
- **FR-027**: Failure to deliver on one channel MUST NOT prevent delivery on other enabled channels and
  MUST be observable; it MUST NOT break unrelated functions.

#### Permissions, Privacy & Audit
- **FR-028**: Every communication MUST be bounded by the recipient's permissions and privacy; it MUST
  NOT surface data the recipient may not see, MUST NOT expose another user's Private data, and MUST NOT
  contain secrets.
- **FR-029**: If a recipient loses permission to the subject before delivery, the communication MUST be
  withheld or redacted on next evaluation.
- **FR-030**: Notification history and pending/undelivered communications MUST follow the privacy/
  deletion lifecycle (anonymized/removed at final account deletion as applicable).
- **FR-031**: Sensitive admin-rule configuration changes to the notification system MUST be audited
  (actor, action, timestamp, context, result).

#### Resilience & Observability
- **FR-032**: The notification system MUST avoid flooding a user (batching/throttling within policy)
  while NEVER silently dropping critical Alerts.
- **FR-033**: Delivery outcomes and engine failures MUST be observable and actionable rather than
  silent, and a notification-system failure MUST NOT break unrelated portal functions.

### Worked Example — Scheduled maintenance (J-1 / H-1 / start)

A maintenance is scheduled by an authorized actor for tomorrow:

1. **WHEN** the schedule reaches J-1 (one day before) **IF** the user is in the permitted audience and
   has not disabled the maintenance category **THEN** produce a day-before Notification on the enabled
   channels (e.g., portal + email).
2. **WHEN** the schedule reaches H-1 (one hour before) **IF** still relevant **THEN** produce an
   hour-before Notification (possibly higher priority).
3. **WHEN** `maintenance.started` fires **IF** relevant **THEN** produce an immediate Notification/Alert
   (the start signal is treated with Alert-level urgency).
4. Dedup ensures each user receives each of the three at most once; preferences and permissions are
   respected; reduced-motion/sound-off suppress animation/sound only.
5. If the maintenance is cancelled after J-1 was sent, a cancellation communication is produced
   (FR-021).

Note: the maintenance records and their `maintenance.scheduled/started/ended` events are owned by
Support/Services & Health; this engine only reacts to them.

### Key Entities

- **Notification**: A targeted per-user portal communication with category, priority, read/dismiss
  state, and delivery record; lives in the notification center.
- **Alert**: A high-urgency communication, visually/behaviorally distinct, possibly muting-bypassing per
  policy; still permission/privacy bound.
- **News (referenced)**: Editorial broadcast content (owned by News); may trigger Notifications.
- **Email Delivery**: An out-of-portal delivery of a communication via the email channel, governed by
  email preferences/policy.
- **Notification Category**: A grouping users can control per channel within policy.
- **Priority**: The urgency level influencing ordering/presentation.
- **Notification Preference**: Per-category, per-channel user choice (retained under policy override).
- **Communication Rule**: An Automation rule (owned by spec 019) whose action produces a communication;
  sourced from automatic/system, admin rules, events, or automations. Notifications defines the
  communication action and delivery, not the engine.
- **Delivery / Delivery Outcome**: A record of a communication sent on a channel and its result
  (delivered/failed), observable.
- **Channel**: portal, email, sound (push in future).
- **Permission/Privacy/Theme (referenced)**: Gating and presentation, owned by their specs.
- **Automation / Maintenance / Event (referenced)**: Trigger sources owned by their specs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Notification, Alert, News, and Email are conflated in data/UI/logic in 0% of cases.
- **SC-002**: An Alert is presented/handled with higher urgency than an ordinary Notification in 100%
  of cases and never bypasses permissions/privacy.
- **SC-003**: User per-category, per-channel preferences are honored on the next matching communication
  in 100% of cases; disabling a category on one channel disables it on other channels in 0% of cases.
- **SC-004**: Policy-mandated categories (e.g., critical Alerts) are user-disabled in 0% of cases; the
  underlying preference is erased in 0% of cases.
- **SC-005**: The WHEN→IF→THEN engine produces a duplicate communication for the same logical
  occurrence in 0% of cases (idempotent), across event/schedule/automation/admin sources.
- **SC-006**: For a scheduled maintenance, a J-1, an H-1, and a start communication are each produced
  once per permitted user in 100% of nominal cases, respecting preferences.
- **SC-007**: Reduced-motion suppresses animation in 100% of cases and sound-off suppresses sound in
  100% of cases, while the communication/urgency is still conveyed in 100% of cases.
- **SC-008**: A theme change alters a communication's urgency/meaning/delivery in 0% of cases (only
  appearance changes).
- **SC-009**: A communication surfaces data beyond the recipient's permissions/privacy in 0% of cases;
  no secrets appear in payloads in 100% of cases.
- **SC-010**: Failure to deliver on one channel prevents delivery on other enabled channels in 0% of
  cases; critical Alerts are silently dropped in 0% of cases; failures are observable in 100% of cases.

## Assumptions

- News editorial authoring/publication is owned by the News module; this spec treats News as a distinct
  concept and a possible trigger source.
- The Automations engine is owned by the Automations spec; this spec provides the communication action
  and consumes automation triggers; automation permission-bounding and execution history live there.
- Maintenance/Incident records and their events are owned by Support/Services & Health; this engine
  reacts to them.
- The authorization, privacy/visibility, theming, and event/history engines are owned by their specs;
  this spec composes with them.
- The exact priority levels and the baseline category taxonomy are configurable; this spec requires
  their existence and that users can control them where policy allows. (Flagged as OQ-45.)
- Push notifications are a future channel; current scope requires portal, email, and sound.

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation.

- **OQ-45 (Priority & category taxonomy)**: Confirm the baseline set of priority levels and notification
  categories, and which categories are policy-mandated (non-disable-able, e.g., critical Alerts).
- **OQ-46 (Late/missed schedule evaluation)**: Confirm how J-1/H-1 triggers behave if evaluated late
  (system downtime): fire-once-if-still-relevant vs skip-if-window-passed, and the relevance window.
- **OQ-47 (Change/cancellation communications)**: Confirm the required corrective communications when a
  scheduled event (e.g., maintenance) is rescheduled or cancelled after reminders were sent.
- **OQ-48 (Throttling/batching policy)**: Confirm the anti-flood policy (batching/throttling/digest)
  and its interaction with Alert urgency (what may never be throttled).
- **OQ-49 (Alert mute-bypass boundary)**: Confirm exactly which mutes a critical Alert may bypass and
  which it may not, to balance urgency against user control.

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference) and the project
  Constitution (v1.0.0).
- Composes with: `specs/003-roles-permissions/spec.md` (recipient gating; admin-rule auditing),
  `specs/004-portal-core-shell/spec.md` (shell notification surface; presentation/degraded states),
  `specs/007-events-history/spec.md` (event triggers; idempotency/`occurred_at`), and
  `specs/009-dashboard-widgets/spec.md` (Events/Since-Last-Login surfacing).
- Depends on / references: `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`,
  `ux/UX_PRINCIPLES.md`, `ux/DESIGN_SYSTEM.md`, `ux/THEMING.md`.
- Related specs (not owned here): News (editorial content), Automations (WHEN/IF/THEN automation
  engine and execution history), Support/Services & Health (Maintenance/Incident sources), the
  Personalization/Themes/A11y spec (022) (presentation), and the Privacy spec (021) (visibility engine).
