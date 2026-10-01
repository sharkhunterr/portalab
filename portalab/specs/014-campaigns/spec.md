# Feature Specification: Events / Campaigns

**Feature Branch**: `014-campaigns`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Detailed functional specification of the Events / Campaigns system. An Event is a temporary campaign/contextualization of the portal."

## Role of This Document

This is a **detailed feature specification** for Events / Campaigns — time-bound themed operations
(e.g., Halloween) that temporarily contextualize the portal: applying XP/Coin/Contribution multipliers,
adding achievements/quests, changing theme/UI, and driving notifications/emails, all under conditions,
with deterministic conflict resolution when multiple campaigns overlap. It conforms to and refines the
superior reference specification (`specs/001-portal-global-spec/spec.md`) and composes with Roles &
Permissions (`specs/003-roles-permissions/spec.md`), Events & History (`specs/007-events-history/spec.md`),
Notifications (`specs/010-notifications/spec.md`), Content/Calendar (`specs/011-content-news-wiki-calendar/spec.md`),
and Gamification & Economy (`specs/013-gamification-economy/spec.md`), under the project Constitution
(`.specify/memory/constitution.md`, v1.0.0). It draws on `product/PRODUCT_BLUEPRINT.md`,
`product/BUSINESS_RULES.md`, `ux/THEMING.md`, and `architecture/EVENT_MODEL.md`.

### Terminology (normative — resolves OQ-1)

Per the global spec, "Event" is overloaded. In this document:

- **Campaign** = the thing this spec owns: a temporary, themed, time-bound contextualization of the
  portal (what the Blueprint calls an "Event"). Halloween is a Campaign.
- **Domain Event** = a recorded fact in the Events & History backbone (e.g., `media.playback_finished`).

This document says **Campaign** for the entity and **Domain Event** for the backbone fact. "Events /
Campaigns" in the title refers to the Campaign concept.

Scope boundary: this spec **owns** the Campaign lifecycle (start/end/duration/recurrence/activation),
its modifier definitions (XP/Coin/Contribution multipliers), its conditions (genres, media, users,
activities, titles), its campaign-scoped achievements/quests, its theme/UI contextualization, and the
**deterministic conflict-resolution rule** for overlapping campaigns. It **does not** own the reward
granting/ledger/anti-abuse mechanics (owned by Gamification & Economy — this spec supplies modifiers
that the reward engine applies), the notification delivery (owned by Notifications — this spec triggers
communications), the theming engine (owned by Theming — this spec selects a theme context), or the
Calendar (which displays campaigns). It chooses no technology and contains no implementation detail.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Define a campaign with a schedule, duration, and recurrence (Priority: P1)

An administrator defines a campaign (e.g., Halloween) with a start, end, duration, and optional
recurrence; it activates automatically within its window and deactivates when it ends.

**Why this priority**: The scheduled lifecycle is the foundation of a campaign; without reliable
start/end/recurrence/activation, nothing else matters.

**Independent Test**: Create a campaign with a start/end (and a recurrence); confirm it becomes active
at start, inactive at end, recurs per its rule, and that activation/deactivation emit events.

**Acceptance Scenarios**:

1. **Given** a campaign with a start and end, **When** the start time is reached, **Then** it becomes
   active and emits `campaign.started`; **When** the end time is reached, **Then** it becomes inactive
   and emits `campaign.ended`.
2. **Given** a recurrence rule (e.g., yearly), **When** the next occurrence is due, **Then** the
   campaign activates again per the rule without manual recreation.
3. **Given** a defined duration, **When** the campaign activates, **Then** it stays active exactly for
   its window.

### User Story 2 - Manual activation/deactivation (Priority: P2)

An authorized admin can manually activate or deactivate a campaign outside or within its schedule
(e.g., enable early, end early), as a permissioned, audited action.

**Why this priority**: Operators need manual override for launches/incidents; it must be controlled and
auditable.

**Independent Test**: Manually activate a scheduled-later campaign and confirm it becomes active;
manually deactivate an active one and confirm it stops applying; confirm both are audited.

**Acceptance Scenarios**:

1. **Given** admin permission, **When** a campaign is manually activated, **Then** it becomes active and
   the action is audited.
2. **Given** an active campaign, **When** it is manually deactivated, **Then** it stops applying its
   modifiers/theme and the action is audited.
3. **Given** a manual override, **When** it conflicts with the schedule, **Then** the override takes
   effect and is recorded (schedule vs manual precedence is defined).

### User Story 3 - Apply XP / Coin / Contribution multipliers via conditions (Priority: P1)

While a campaign is active, qualifying activities receive XP/Coin/Contribution multipliers defined by
the campaign's conditions (genres, media, titles, activities, users); the reward engine applies them.

**Why this priority**: Multipliers under conditions are the primary mechanic and the heart of the
Halloween example.

**Independent Test**: With Halloween active, perform a qualifying activity (watch a horror movie);
confirm the reward engine applies the defined multipliers (XP x2, Coins x1.5) to the grant, and that a
non-qualifying activity is unaffected.

**Acceptance Scenarios**:

1. **Given** an active campaign with a condition "horror movie watched → XP x2, Coins x1.5", **When** a
   user finishes a horror movie, **Then** the reward engine applies XP x2 and Coins x1.5 to that grant.
2. **Given** a condition "title contains 'Halloween' → XP x2", **When** such a title is consumed,
   **Then** XP x2 applies.
3. **Given** a non-qualifying activity, **When** performed, **Then** no campaign multiplier applies.
4. **Given** a multiplier applies, **When** the reward is granted, **Then** Gamification's anti-farming
   (cooldown/caps/diminishing) still applies (campaign does not bypass anti-abuse).

### User Story 4 - Campaign conditions across genres, media, users, activities (Priority: P1)

A campaign's conditions can match on genre, media type (movie/game/book/etc.), title text, activity
type, and user/audience criteria, so the same campaign rewards multiple qualifying behaviors.

**Why this priority**: The Halloween example explicitly spans movies, games, books, and titles; the
condition model must support all of them.

**Independent Test**: Define Halloween conditions for horror movie / horror game / horror book / title
contains Halloween; perform each; confirm each qualifies and receives the defined multipliers; confirm
audience/user conditions scope who is affected.

**Acceptance Scenarios**:

1. **Given** conditions for horror movie, horror game, and horror book (each XP x2, Coins x1.5), **When**
   a user performs any of them, **Then** the matching multipliers apply.
2. **Given** a user/audience condition, **When** a user outside the audience performs a qualifying
   activity, **Then** the campaign does not apply to them.
3. **Given** a media/genre condition, **When** evaluated, **Then** matching uses the item's attributes
   via capabilities (not a hard-coded service).

### User Story 5 - Campaign achievements, quests, theme/UI, notifications, emails (Priority: P2)

A campaign can add its own achievements and quests, apply a theme/UI contextualization, and trigger
notifications and emails about the campaign — all within permissions, preferences, and the locked
"theme changes presentation only" rule.

**Why this priority**: These make a campaign feel like an occasion; they must integrate with existing
engines (Gamification, Theming, Notifications) not parallel ones.

**Independent Test**: Activate a campaign that defines an achievement, a quest, a theme, and launch
notifications/emails; confirm the achievement/quest appear and grant via Gamification, the theme changes
only presentation, and communications respect preferences/permissions.

**Acceptance Scenarios**:

1. **Given** a campaign defining an achievement/quest, **When** active, **Then** they are available and
   grant via Gamification (not a parallel reward mechanism).
2. **Given** a campaign theme/UI, **When** active, **Then** presentation changes while permissions,
   business rules, source-of-truth, and functional state are unchanged (theme changes presentation
   only); accessibility preferences still take precedence.
3. **Given** campaign notifications/emails, **When** triggered, **Then** they are produced via the
   notification engine, respecting user preferences and permissions.

### User Story 6 - Multiple simultaneous campaigns with deterministic conflict resolution (Priority: P1)

When multiple campaigns are active at once and apply to the same activity, their modifiers combine by a
single deterministic configured rule, with duplicate rewards prevented and anti-farming still enforced.

**Why this priority**: "Multiple events may overlap; conflict resolution is deterministic" is a locked
rule; ambiguous stacking would make rewards unpredictable and exploitable.

**Independent Test**: Activate two overlapping campaigns that both match an activity; confirm their
modifiers combine by the configured deterministic rule (with a defined order), produce a single
reproducible result, no duplicate reward, and anti-farming still applies.

**Acceptance Scenarios**:

1. **Given** two active campaigns both matching an activity, **When** a reward is granted, **Then** the
   modifiers combine by the configured deterministic rule and the result is reproducible.
2. **Given** overlapping campaigns, **When** combined, **Then** the same occurrence yields no duplicate
   reward and the combination order is defined (not arbitrary).
3. **Given** a configured cap on total campaign boost, **When** combined modifiers would exceed it,
   **Then** the cap applies deterministically.
4. **Given** overlapping campaigns, **When** applied, **Then** Gamification anti-farming still bounds the
   outcome.

### User Story 7 - Anti-farming and integrity within campaigns (Priority: P1)

Campaign boosts never bypass anti-abuse: cooldowns, caps, diminishing returns, and anomaly handling from
Gamification still apply, and duplicate rewards for the same occurrence are prevented even across
multipliers and overlapping campaigns.

**Why this priority**: Campaigns multiply rewards, which is exactly where farming risk concentrates;
integrity must hold.

**Independent Test**: During an active campaign, attempt to farm a boosted reward; confirm cooldown/
caps/diminishing/anomaly rules still bound it and no duplicate reward occurs.

**Acceptance Scenarios**:

1. **Given** an active campaign multiplier, **When** a user repeats a boosted activity rapidly, **Then**
   cooldown/caps/diminishing returns still apply to the boosted grant.
2. **Given** an anomalous boosted earning pattern, **When** detected, **Then** it is handled per
   Gamification anti-abuse policy and recorded.
3. **Given** a single qualifying occurrence, **When** multiple multipliers/campaigns match, **Then** the
   reward is granted once (combined), never duplicated.

### User Story 8 - Campaign history and rule versioning (Priority: P2)

Past campaigns and the rewards they produced are historized and bound to the campaign/rule version in
force at the time; changing or ending a campaign never rewrites historical grants.

**Why this priority**: Consistent with the locked "historical rules/transactions not rewritten"
principle; campaign changes must not retroactively alter history.

**Independent Test**: Run a campaign, grant boosted rewards, then modify/end the campaign; confirm
historical grants retain their original campaign/rule version and are not reinterpreted.

**Acceptance Scenarios**:

1. **Given** rewards granted under a campaign, **When** the campaign later changes or ends, **Then** the
   historical grants remain bound to the version in force when granted.
2. **Given** campaign history, **When** viewed, **Then** it shows when the campaign was active and which
   version applied, without rewriting past transactions.

### Edge Cases

- **Overlapping campaigns on one activity**: Modifiers combine by the configured deterministic rule
  with a defined order; result is reproducible; no duplicate reward.
- **Boost cap exceeded**: If combined multipliers exceed a configured maximum total boost, the cap
  applies deterministically.
- **Campaign ends mid-activity**: Eligibility is evaluated at the activity's `occurred_at`; an activity
  occurring within the window qualifies even if processed slightly after end (late event), per Events &
  History attribution.
- **Manual override vs schedule**: Manual activation/deactivation precedence over the schedule is
  defined and recorded; when the override is cleared, the schedule resumes.
- **Recurrence collision**: A recurring campaign overlapping a one-off campaign is treated like any
  overlap (deterministic combination), not a special case.
- **Condition matches via disconnected service**: Matching uses historized/capability attributes; if a
  source is unavailable, evaluation uses available data and degrades gracefully (no crash, no false
  grant).
- **Title/genre ambiguity**: Condition matching rules (case, substring vs exact, locale) are defined so
  "title contains Halloween" is deterministic.
- **Multiplier on Contribution**: Contribution multipliers apply like XP/Coins but still respect
  Contribution anti-abuse.
- **Anti-farming during boost**: Cooldown/caps/diminishing/anomaly still apply to boosted grants;
  campaigns never bypass them.
- **Theme conflict with user/accessibility preference**: Campaign theme changes presentation only;
  accessibility preferences (reduced motion, contrast) still take precedence.
- **Campaign notification storm**: Campaign communications respect the notification engine's
  throttling/preferences; critical items are not dropped, routine ones are batched per policy.
- **Historical replay**: Reconstruction applies the campaign/rule version in force at each grant's
  `occurred_at` and does not re-grant or re-notify (consistent with Events & History).
- **Reward engine ownership**: The campaign supplies modifiers/conditions; the actual grant, ledger,
  and anti-abuse are executed by Gamification (no parallel reward path).

## Requirements *(mandatory)*

### Functional Requirements

#### Campaign Lifecycle (start/end/duration/recurrence/activation)
- **FR-001**: The system MUST allow defining a campaign with a start, end, and/or duration, and MUST
  activate/deactivate it automatically within that window.
- **FR-002**: The system MUST support recurrence (e.g., yearly) so a campaign reactivates per its rule
  without manual recreation.
- **FR-003**: Campaign activation and deactivation MUST emit `campaign.started` / `campaign.ended`
  domain events with `occurred_at` distinct from `received_at`.
- **FR-004**: Authorized admins MUST be able to manually activate/deactivate a campaign; manual
  overrides MUST take a defined precedence over the schedule and MUST be audited.

#### Modifiers (XP / Coin / Contribution multipliers)
- **FR-005**: A campaign MUST be able to define XP, Coin, and Contribution multipliers applied to
  qualifying grants while active.
- **FR-006**: The campaign MUST supply its modifiers/conditions to the Gamification reward engine, which
  performs the actual grant; the campaign MUST NOT implement a parallel reward/ledger mechanism.
- **FR-007**: Campaign multipliers MUST NOT bypass Gamification anti-abuse (cooldown, caps, diminishing
  returns, anomaly handling).

#### Conditions (genres, media, titles, activities, users)
- **FR-008**: A campaign MUST support conditions matching on genre, media type (e.g., movie/game/book),
  title text, activity type, and user/audience criteria.
- **FR-009**: Condition matching MUST use item/activity attributes via capabilities (not hard-coded to a
  specific external service) and MUST be deterministic (defined case/substring/exact/locale semantics).
- **FR-010**: A user/audience condition MUST scope which users the campaign applies to; users outside
  the audience MUST NOT receive the campaign's effects.

#### Campaign Achievements, Quests, Theme/UI, Communications
- **FR-011**: A campaign MUST be able to define campaign-scoped achievements and quests, which are
  granted via Gamification (not a parallel mechanism).
- **FR-012**: A campaign MUST be able to apply a theme/UI contextualization that changes presentation
  only; it MUST NOT change permissions, business rules, source-of-truth, or functional state, and
  accessibility preferences MUST take precedence.
- **FR-013**: A campaign MUST be able to trigger notifications and emails about the campaign, produced
  only via the notification engine, respecting user preferences and permissions.

#### Multiple Simultaneous Campaigns & Deterministic Conflict Resolution
- **FR-014**: The system MUST support multiple campaigns active simultaneously.
- **FR-015**: When multiple active campaigns apply to the same occurrence, their modifiers MUST combine
  by a single configured deterministic rule with a defined order of application; the result MUST be
  reproducible.
- **FR-016**: The combination MUST prevent duplicate rewards for the same occurrence and MUST support a
  configurable maximum total boost cap applied deterministically.
- **FR-017**: The deterministic combination rule MUST be documented and consistent with the rule
  referenced by Gamification (OQ-64) so campaign stacking is unambiguous.

#### Anti-Farming & Integrity
- **FR-018**: All campaign-boosted grants MUST remain subject to Gamification anti-abuse (cooldown,
  caps, diminishing returns, anomaly handling).
- **FR-019**: A single qualifying occurrence matched by multiple multipliers/campaigns MUST be granted
  once (combined), never duplicated.
- **FR-020**: Campaign eligibility MUST be evaluated at the activity's `occurred_at`, so late/duplicate
  events are attributed correctly and idempotently.

#### History & Rule Versioning
- **FR-021**: Campaign definitions and modifiers MUST be versioned; grants made under a campaign MUST
  record the campaign and rule version in force at `occurred_at`.
- **FR-022**: Changing or ending a campaign MUST NOT rewrite or reinterpret historical grants/
  transactions; reconstruction MUST apply the historical version.
- **FR-023**: Campaign history MUST record when each campaign was active and which version applied.

#### Permissions, Audit, Resilience
- **FR-024**: Defining, activating/deactivating, and modifying campaigns MUST be permission-gated
  sensitive actions, confirmed where appropriate and audited (actor, action, timestamp, context,
  result).
- **FR-025**: If a data source needed for condition matching is unavailable, evaluation MUST degrade
  gracefully (use available data, no crash, no false grant) and MUST NOT break unrelated functions.
- **FR-026**: Campaign-related domain events MUST be consumed idempotently where duplicate delivery is
  possible, and no secrets MUST appear in campaign data/events.

### Worked Example — Halloween Campaign

Campaign "Halloween" active for its window defines conditions:

- **Horror movie watched** → XP x2, Coins x1.5
- **Title contains "Halloween"** → XP x2
- **Horror game played** → XP x2, Coins x1.5
- **Horror book read** → XP x2, Coins x1.5

Behavior:

1. When a user finishes a horror movie (`media.playback_finished` with genre = horror), the campaign
   contributes XP x2 and Coins x1.5 to that grant; Gamification applies them and records the
   transaction with the campaign + rule version.
2. If the title also contains "Halloween", both matching conditions apply to the same occurrence; their
   multipliers combine by the configured deterministic rule (e.g., defined as additive or
   multiplicative with a documented order and a max-boost cap) — once, never duplicated.
3. Anti-farming still bounds repeated horror-movie watching (cooldown/cap/diminishing).
4. The campaign may apply a Halloween theme (presentation only) and send a launch notification/email
   per user preferences.
5. After the window ends, the boosts stop; historical grants keep their Halloween version.

Note: the exact combination arithmetic for simultaneously-matching conditions/campaigns is the
deterministic rule of FR-015/017, aligned with Gamification OQ-64 (flagged below as OQ-65).

### Campaign State Model

**States**: Draft, Scheduled, Active, Paused (manually deactivated while within window), Ended,
Archived.

**Transitions**:

- Draft to Scheduled (schedule set) ; Scheduled to Active (start reached or manual activate)
- Active to Ended (end reached or manual end) ; Active to Paused (manual deactivate) ; Paused to Active
  (manual reactivate within window)
- Scheduled/Ended to Active again (recurrence next occurrence)
- Ended to Archived (retained; no longer applies)

**Invariants**:
- A campaign applies modifiers/theme only while Active.
- Manual override precedence over schedule is defined and recorded.
- Overlap of multiple Active campaigns resolves by the single deterministic combination rule.
- Ending/changing a campaign never rewrites historical grants.

### Campaign-Related Domain Events

Names aligned with the Event Model; each carries actor/context, campaign reference, version, metadata.

- `campaign.created`, `campaign.updated`
- `campaign.started` (activation), `campaign.ended` (deactivation)
- `campaign.paused`, `campaign.resumed`
- `campaign.modifier_applied` (reference on a boosted grant, for traceability)

### Key Entities

- **Campaign**: A time-bound themed contextualization with schedule/duration/recurrence, conditions,
  modifiers, campaign achievements/quests, theme/UI, and communications; versioned.
- **Campaign Schedule**: Start/end/duration/recurrence definition and activation state.
- **Condition**: A matcher over genre, media type, title text, activity type, and user/audience.
- **Modifier**: An XP/Coin/Contribution multiplier (and optional boost cap) applied to qualifying
  grants.
- **Combination Rule**: The single deterministic rule governing how overlapping modifiers combine
  (shared with Gamification).
- **Campaign Achievement/Quest (referenced)**: Defined by the campaign, granted via Gamification.
- **Campaign Theme (referenced)**: A presentation-only contextualization applied via Theming.
- **Permission/Notification/Event/Reward engines (referenced)**: Composed with, not owned.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A campaign activates/deactivates within its scheduled window in 100% of cases and recurs
  per its rule in 100% of recurring cases.
- **SC-002**: Qualifying activities receive the campaign's defined multipliers in 100% of matching cases;
  non-qualifying activities receive them in 0% of cases.
- **SC-003**: Overlapping active campaigns produce a non-deterministic or duplicate reward for the same
  occurrence in 0% of cases (single reproducible combined result in 100%).
- **SC-004**: Campaign multipliers bypass Gamification anti-abuse (cooldown/caps/diminishing/anomaly) in
  0% of cases.
- **SC-005**: A campaign implements a parallel reward/ledger or notification mechanism in 0% of cases
  (always via Gamification / Notifications).
- **SC-006**: A campaign theme changes permissions/business-rules/source-of-truth/functional-state in 0%
  of cases (presentation only); accessibility preferences remain in effect in 100% of cases.
- **SC-007**: Changing or ending a campaign rewrites/reinterprets historical grants in 0% of cases
  (historical campaign/rule version applied in 100% of reconstructions).
- **SC-008**: Campaign definition/activation/modification is audited in 100% of cases.
- **SC-009**: A configured maximum total boost cap is exceeded by combined modifiers in 0% of cases.
- **SC-010**: Campaign effects reach users outside a defined audience condition in 0% of cases.

## Assumptions

- The reward granting, ledger, and anti-abuse mechanics are owned by Gamification & Economy
  (`specs/013`); this spec supplies modifiers/conditions the reward engine applies.
- The theming engine is owned by the Personalization/Themes/A11y spec (022); a campaign selects a theme context (presentation
  only). The Calendar (`specs/011`) displays campaigns. Notifications (`specs/010`) deliver campaign
  communications.
- Condition attributes (genre, media type, title) come from the relevant domains via capabilities
  (e.g., Media); this spec defines matching semantics, not each domain's data model.
- The exact deterministic combination arithmetic for overlapping modifiers is shared with Gamification
  (OQ-64) and confirmed here as OQ-65.
- Recurrence granularity and timezone handling for schedules follow admin policy / user locale as
  relevant. (Flagged as OQ-66.)

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation.

- **OQ-65 (Combination arithmetic)**: Confirm the exact deterministic rule for combining overlapping
  multipliers (additive e.g. x2 + x1.5 → x2.5-equivalent, multiplicative x2 * 1.5 = x3, max-wins, or
  priority-ordered) and the order of application — shared with Gamification OQ-64.
- **OQ-66 (Schedule/recurrence semantics)**: Confirm recurrence granularity (yearly/seasonal/custom),
  timezone handling, and how a recurrence interacts with manual overrides.
- **OQ-67 (Max boost cap)**: Confirm whether a global/per-campaign maximum total boost cap exists and
  its default.
- **OQ-68 (Condition matching semantics)**: Confirm title/genre matching semantics (case sensitivity,
  substring vs tag-based, localization) to keep "title contains Halloween" deterministic.
- **OQ-69 (Manual override precedence)**: Confirm the precedence and recording when a manual activation/
  deactivation conflicts with the schedule, and whether overrides auto-expire.

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference) and the project
  Constitution (v1.0.0).
- Composes with: `specs/003-roles-permissions/spec.md` (`events.manage` / campaign permissions; audit),
  `specs/007-events-history/spec.md` (campaign events, `occurred_at` attribution, reconstruction,
  versioning), `specs/010-notifications/spec.md` (campaign notifications/emails),
  `specs/011-content-news-wiki-calendar/spec.md` (Calendar displays campaigns), and
  `specs/013-gamification-economy/spec.md` (reward engine applies modifiers; anti-abuse; ledger; rule
  versioning — OQ-64 combination rule).
- Depends on / references: `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`, `ux/THEMING.md`,
  `architecture/EVENT_MODEL.md`.
- Related specs (not owned here): Gamification & Economy (grants/ledger/anti-abuse), Theming
  (presentation), Media and other domains (condition attributes via capabilities), Notifications
  (delivery), and Calendar (display).
