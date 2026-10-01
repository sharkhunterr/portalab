# Feature Specification: Community

**Feature Branch**: `012-community`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Detailed functional specification of the Community module."

## Role of This Document

This is a **detailed feature specification** for the Community module — members, profiles, activity,
leaderboards, achievements, quests, challenges, community projects (proposals, voting, funding),
contribution, user help, and discovery. It conforms to and refines the superior reference
specification (`specs/001-portal-global-spec/spec.md`) and composes with Identity & Users
(`specs/002-identity-users/spec.md`), Roles & Permissions (`specs/003-roles-permissions/spec.md`),
the Portal Core shell (`specs/004-portal-core-shell/spec.md`), Events & History
(`specs/007-events-history/spec.md`), and Notifications (`specs/010-notifications/spec.md`), under the
project Constitution (`.specify/memory/constitution.md`, v1.0.0). It draws on
`product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`, `ux/UX_PRINCIPLES.md`, and
`ux/USER_JOURNEYS.md`.

Scope boundary: this spec owns the **Community module surfaces and rules** — members directory,
community profile presentation, activity feed, leaderboards, achievements/quests/challenges display,
community projects with proposals/voting/funding, contribution accounting rules (as they relate to
community value), user-to-user help, and discovery. It **consumes** the gamification engines (XP,
Contribution, Coins, achievement/quest definitions and reward logic are owned by the Gamification
spec), the economy ledger (Coins transactions owned by the Economy spec), and the authorization/
privacy/notification/event engines. It does **not** re-define those engines. It chooses no technology
and contains no implementation detail.

### Explicit Non-Goals (normative — MUST NOT be built here)

Per the locked product decision "no core friends/followers/DM/chat system", this module MUST NOT
introduce:

- **Friends** or **followers** relationships;
- a **social network** graph;
- **direct messages (DM)**;
- **likes** / reaction counters;
- a **native chat**.

Chat MAY be added later **as a plugin** (via the extension model); it is explicitly out of scope for
the core Community module. Community interaction happens through shared surfaces (projects, activity,
leaderboards, help) — not through a personal social graph.

**Terminology**: Vote = a free expression of support on a community project by any active account;
Funding = a separate, Coins-based contribution to a project; Contribution = the tracked community-value
metric (owned by Gamification); Domain Event = a recorded fact.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Members directory and community profiles within visibility (Priority: P1)

A user browses the members directory and views community profiles; each profile shows only what its
owner's visibility settings and the viewer's permissions allow — never another user's private data by
permission alone.

**Why this priority**: Members and profiles are the identity surface of the community; getting
visibility right is foundational and privacy-critical.

**Independent Test**: As viewers with different permissions, browse members and open profiles; confirm
each sees only permitted/visible fields, that Private fields never appear by permission alone, and that
there is no friends/followers construct anywhere.

**Acceptance Scenarios**:

1. **Given** community profiles with varied visibility (Public, Community, Leaderboard-only, Private),
   **When** a viewer browses, **Then** they see only fields allowed by the owner's visibility and the
   viewer's permissions.
2. **Given** a Private profile field, **When** any viewer looks, **Then** it is not shown by permission
   alone (privacy honored).
3. **Given** the members/profile surfaces, **When** inspected, **Then** no friends, followers, DM,
   likes, or chat affordances exist.

### User Story 2 - Activity feed from events within visibility (Priority: P2)

A user sees a community activity feed derived from domain events (achievements unlocked, projects
progressing, media/community milestones) — each entry shown only to those permitted and within the
actor's visibility, with no likes/reactions.

**Why this priority**: Activity is how the community feels alive; it must be event-sourced and
visibility-bounded, not a social reaction system.

**Independent Test**: Generate activity-producing events; view the feed as different users; confirm
entries appear only within visibility/permissions, reference their source, and offer no like/reaction/
comment-as-social affordance.

**Acceptance Scenarios**:

1. **Given** activity-producing events, **When** the feed is viewed, **Then** permitted entries appear,
   each referencing its source and respecting the actor's visibility.
2. **Given** an actor set to Private/Leaderboard-only for an activity type, **When** the feed renders,
   **Then** that activity is not surfaced beyond the allowed audience.
3. **Given** the activity feed, **When** inspected, **Then** it has no likes/reactions/DM affordances.

### User Story 3 - Leaderboards respecting visibility (Priority: P2)

A user views leaderboards (e.g., XP, Contribution) that rank participating accounts; a user who opted
out of leaderboards (visibility = not-on-leaderboard) is excluded, and private data is never exposed.

**Why this priority**: Leaderboards drive engagement but must honor the dedicated "Leaderboard only"
and opt-out visibility semantics.

**Independent Test**: Populate scores; set one account to exclude itself from leaderboards; view the
board; confirm the opted-out account is absent and that only permitted, non-private data is shown.

**Acceptance Scenarios**:

1. **Given** participating accounts, **When** a leaderboard is viewed, **Then** it ranks them by the
   metric while honoring each account's leaderboard visibility.
2. **Given** an account that opted out of leaderboards, **When** the board renders, **Then** it is
   excluded.
3. **Given** leaderboard entries, **When** shown, **Then** no private data is exposed by permission
   alone.

### User Story 4 - Achievements, quests, challenges display (Priority: P2)

A user sees their achievements, available quests, and challenges, and community-wide achievement
activity within visibility; definitions and reward logic come from Gamification, Community presents and
contextualizes them.

**Why this priority**: These drive progression and community participation; Community is their primary
presentation surface while Gamification owns the rules.

**Independent Test**: With achievements/quests/challenges defined in Gamification, view them in
Community; confirm the user sees their status and permitted community achievement activity, and that
Community does not re-define reward rules.

**Acceptance Scenarios**:

1. **Given** achievements/quests/challenges defined by Gamification, **When** viewed in Community,
   **Then** the user sees their own status and progress and permitted community achievement activity.
2. **Given** a locked/secret achievement, **When** displayed, **Then** it respects its reveal rules and
   the viewer's permissions.
3. **Given** Community display, **When** rendered, **Then** it reflects Gamification's definitions
   without re-defining reward logic (no parallel mechanism).

### User Story 5 - Community projects: propose, vote (free), fund (Coins) (Priority: P1)

A user proposes a community project; any active account can vote for free; separately, users may fund
the project with Coins. Voting and funding are independent, and funding does not guarantee
implementation.

**Why this priority**: Community projects are the Marketplace/community convergence point and encode
several locked rules (all active accounts vote, voting free, funding separate and Coins-based, funding
≠ implementation).

**Independent Test**: Propose a project; vote as several active accounts (confirm free, no minimum
level); fund with Coins as some users; confirm voting and funding are independent and that funding does
not mark the project as guaranteed.

**Acceptance Scenarios**:

1. **Given** an active account, **When** they vote on a project, **Then** the vote is accepted for free
   with no minimum level, and a `project.vote_added` event is recorded.
2. **Given** a user with Coins, **When** they fund a project, **Then** a Coins transaction is recorded
   (owned by Economy) and a `project.funding_added` event is recorded, independently of any vote.
3. **Given** a funded project, **When** viewed, **Then** funding does not guarantee implementation;
   reserved funds follow the project's published rules (refunded or consumed).
4. **Given** a non-active account (e.g., inactive/suspended/pending-deletion), **When** they attempt to
   vote, **Then** it is refused (only active accounts vote).
5. **Given** voting and funding, **When** compared, **Then** they are independent — voting is never
   required to fund and funding never counts as a vote.

### User Story 6 - Community project lifecycle and proposals (Priority: P2)

A community project moves through a clear lifecycle (proposed → under consideration → accepted/declined
→ in progress → delivered/closed) with transparent status; proposals are reviewed per policy and
status changes are communicated.

**Why this priority**: Projects need a transparent, auditable lifecycle so votes/funding have meaning
and users understand outcomes.

**Independent Test**: Take a proposal through the lifecycle; confirm each status is visible, status
changes emit events and may notify interested users, and that reserved funds resolve per published
rules at terminal states.

**Acceptance Scenarios**:

1. **Given** a proposal, **When** it progresses, **Then** its status is transparent and each change
   emits a `project.status_changed` event.
2. **Given** a status change, **When** it occurs, **Then** interested/permitted users MAY be notified
   via the notification engine per their preferences.
3. **Given** a project reaches a terminal state, **When** it closes, **Then** reserved funds are
   refunded or consumed per the project's published rules, recorded as Economy transactions.

### User Story 7 - Contribution and user-to-user help (Priority: P2)

Users help each other (e.g., answering questions, contributing to Wiki/projects); valuable
contributions are recognized via the Contribution metric per Gamification rules, within anti-abuse
limits.

**Why this priority**: Contribution is one of the three tracked values and the community's
value-recognition mechanism; user help is explicitly in scope (distinct from a chat/social system).

**Independent Test**: Perform a recognized helpful contribution; confirm Contribution is granted per
Gamification rules (deterministic, audited for manual grants), within anti-abuse limits, and attributed
correctly.

**Acceptance Scenarios**:

1. **Given** a recognized helpful contribution, **When** it occurs, **Then** Contribution is granted per
   Gamification's deterministic rules and attributed to the contributor.
2. **Given** anti-abuse limits, **When** repeated/gamed contributions are attempted, **Then** duplicate
   or farmed Contribution is prevented.
3. **Given** user-to-user help, **When** provided, **Then** it occurs through community surfaces
   (projects, help prompts, Wiki) — not through DMs/chat/social follows.

### User Story 8 - Discovery of community content (Priority: P3)

A user discovers members, projects, achievements, and activity through discovery surfaces and global
search, all scoped to permissions and visibility, with no dead-ends.

**Why this priority**: Discovery turns the community from a static list into something explorable,
reinforcing the one-environment feel.

**Independent Test**: Use discovery and global search for community content; confirm permitted items
surface grouped sensibly, unpermitted/private items do not, and empty results offer a relevant next
action.

**Acceptance Scenarios**:

1. **Given** community content, **When** a user uses discovery/search, **Then** permitted items surface
   within visibility and unpermitted/private items do not.
2. **Given** no results, **When** discovery renders, **Then** a relevant next action is offered (no
   dead-end).

### Edge Cases

- **Non-active account voting**: Inactive, Suspended, Pending-Deletion, or Deleted accounts cannot vote;
  only Active accounts are "active accounts" for voting eligibility.
- **Double voting**: A user voting twice on the same project does not produce two votes (idempotent; one
  vote per account per project unless the project rules define otherwise).
- **Funding with insufficient Coins**: Funding is refused if the user lacks Coins; the Coin balance
  never goes negative (Economy rule); no partial corruption.
- **Vote-to-fund conflation attempt**: Voting never deducts Coins; funding never counts as a vote; the
  two ledgers are separate.
- **Project declined/cancelled with reserved funds**: Reserved funds are refunded or consumed strictly
  per the project's published rules, as new Economy transactions (never retroactive edits).
- **Visibility opt-out**: A user excluded from leaderboards/activity by their visibility is omitted,
  while their own view still shows their own data.
- **Private profile vs community metric**: A user may appear on a leaderboard by metric while keeping
  profile details Private; the metric exposure follows their leaderboard visibility, not full profile
  disclosure.
- **Achievement reveal rules**: Secret/locked achievements respect their reveal rules and the viewer's
  permissions; community activity never leaks a not-yet-revealed achievement.
- **Contribution farming**: Repeated/low-value or self-dealing contributions are limited by anti-abuse
  rules; duplicate Contribution is prevented.
- **Help without social graph**: User-to-user help never requires or creates friends/followers/DM; it
  is mediated by shared surfaces.
- **Chat expectation**: Any chat capability is absent from core; if later added as a plugin it must not
  be assumed present by core Community flows.
- **Permission/visibility change mid-session**: Community surfaces re-evaluate on next load; newly
  unpermitted content disappears; privacy is honored independently.
- **Deleted/anonymized member**: After account deletion, the member's identifying presence is
  removed/anonymized while integrity-necessary records (e.g., vote/funding counts, transactions) are
  preserved in non-identifying form.

## Requirements *(mandatory)*

### Functional Requirements

#### Members & Profiles
- **FR-001**: The system MUST provide a members directory and community profiles that display only
  fields allowed by the owner's visibility (Public, Community, Leaderboard-only, Private) and the
  viewer's permissions.
- **FR-002**: Community surfaces MUST NOT expose another user's Private data by permission alone;
  privacy is a separate, non-overridable gate.
- **FR-003**: The Community module MUST NOT implement friends, followers, a social graph, direct
  messages, likes/reactions, or a native chat.
- **FR-004**: Chat, if introduced later, MUST be an optional plugin via the extension model; core
  Community flows MUST NOT assume its presence.

#### Activity
- **FR-005**: The system MUST provide a community activity feed derived from domain events, showing each
  entry only to permitted viewers and within the actor's visibility.
- **FR-006**: The activity feed MUST reference each entry's source and MUST NOT provide likes/reactions/
  social-follow affordances.

#### Leaderboards
- **FR-007**: The system MUST provide leaderboards ranking participating accounts by a metric (e.g., XP,
  Contribution) while honoring each account's leaderboard visibility, including opt-out.
- **FR-008**: Leaderboards MUST NOT expose private data by permission alone and MUST exclude accounts
  that opted out of leaderboards.

#### Achievements, Quests, Challenges (presentation)
- **FR-009**: The system MUST present achievements, quests, and challenges (defined by Gamification),
  showing the user's own status/progress and permitted community achievement activity.
- **FR-010**: Secret/locked achievements MUST respect their reveal rules and the viewer's permissions.
- **FR-011**: Community MUST reflect Gamification's definitions and reward logic without re-defining
  them (no parallel reward mechanism).

#### Community Projects — Proposals, Voting, Funding
- **FR-012**: Any user MUST be able to propose a community project (subject to permission/policy), and
  proposals MUST have a transparent, reviewable status.
- **FR-013**: Every Active account MUST be able to vote on a community project for free, with no minimum
  level; non-active accounts MUST be refused.
- **FR-014**: Voting MUST be idempotent (one vote per account per project unless the project rules
  explicitly allow otherwise) and MUST record a `project.vote_added` event.
- **FR-015**: Users MUST be able to fund a project with Coins; funding MUST record an Economy
  transaction and a `project.funding_added` event, independently of voting.
- **FR-016**: Voting and funding MUST be independent: voting MUST NOT cost Coins and funding MUST NOT
  count as a vote.
- **FR-017**: Funding MUST NOT guarantee implementation; reserved funds MUST be refunded or consumed per
  the project's published rules, recorded as new Economy transactions (never retroactive edits).
- **FR-018**: Funding MUST be refused if the user has insufficient Coins; the balance MUST NOT go
  negative.

#### Community Project Lifecycle
- **FR-019**: A community project MUST have a clear lifecycle (e.g., Proposed → Under Consideration →
  Accepted/Declined → In Progress → Delivered/Closed) with transparent status.
- **FR-020**: Each status change MUST emit a `project.status_changed` event and MAY notify interested/
  permitted users via the notification engine per their preferences.
- **FR-021**: At a terminal state, reserved funds MUST resolve per the project's published rules.

#### Contribution & User Help
- **FR-022**: Recognized helpful contributions MUST grant Contribution per Gamification's deterministic
  rules, attributed to the contributor, within anti-abuse limits that prevent duplicate/farmed
  Contribution.
- **FR-023**: User-to-user help MUST occur through shared community surfaces (projects, help prompts,
  Wiki) and MUST NOT require or create friends/followers/DM/chat.
- **FR-024**: Manual Contribution grants MUST be marked and audited (consistent with Gamification).

#### Discovery
- **FR-025**: The system MUST provide discovery of community content (members, projects, achievements,
  activity), scoped to permissions/visibility, integrated with Global Search, with no dead-end empty
  states.

#### Visibility, Permissions, Events, Notifications, History
- **FR-026**: All Community surfaces MUST be gated by the authorization engine (deny-by-default,
  server-side) and MUST respect privacy and admin visibility policies (permissions never override
  privacy).
- **FR-027**: Community actions MUST emit domain events (e.g., `project.created`, `project.vote_added`,
  `project.funding_added`, `project.status_changed`, `achievement.unlocked`, `quest.completed`) with
  `occurred_at` distinct from `received_at`; consumers MUST be idempotent where duplicates are possible.
- **FR-028**: Community history MUST be retained with provenance; historized community data MUST NOT be
  automatically public and MUST follow the privacy/deletion lifecycle (identifying data anonymized/
  removed at final deletion; integrity counts/transactions preserved non-identifying).
- **FR-029**: Sensitive community actions (e.g., project status changes by moderators/admin, manual
  Contribution grants, fund consumption) MUST be audited with actor, action, timestamp, context, result.
- **FR-030**: Community notifications MUST be produced only via the notification engine, respecting
  recipient preferences and permissions (no parallel notification mechanism).

#### Resilience
- **FR-031**: Community surfaces MUST degrade gracefully: if a source (e.g., Gamification, Economy, a
  service) is slow/unavailable, affected sections show their functional state while the rest remains
  usable.

### Community Project State Model

**States**: Proposed, Under Consideration, Accepted, Declined, In Progress, Delivered, Closed.

**Transitions** (gated by permission/policy):

- Proposed to Under Consideration (review begins)
- Under Consideration to Accepted or Declined (decision per policy; votes/funding inform but do not
  bind)
- Accepted to In Progress to Delivered (implementation lifecycle)
- Delivered/Declined to Closed (terminal; reserved funds resolved per published rules)

**Invariants**:
- Voting is free, available to every Active account, with no minimum level.
- Funding is separate from voting and uses Coins; funding never guarantees acceptance/implementation.
- Reserved funds resolve only per the project's published rules, as new Economy transactions.
- A declined/closed project never silently consumes funds without following its published rules.

### Contribution Rules (community-facing)

- Contribution recognizes community value (helping users, advancing projects, valuable content).
- Contribution is granted by Gamification's deterministic rules; Community provides the recognized
  actions/surfaces, not a separate reward engine.
- Anti-abuse: duplicate rewards prevented; farming/self-dealing limited; manual grants marked/audited.
- Contribution is one of the three tracked values (XP, Contribution, Coins) and is never conflated with
  Coins or XP.

### Community-Related Domain Events

Names aligned with the Event Model; each carries actor/context, subject reference, metadata, version.

- `project.created`, `project.vote_added`, `project.funding_added`, `project.status_changed`
- `achievement.unlocked`, `quest.completed`, `reward.granted` (Contribution; owned by Gamification)
- `community.activity_recorded` (activity-feed point, within visibility)

### Key Entities

- **Member**: A user's community-facing presence (links to the User identity; no friends/followers).
- **Community Profile**: The visibility-scoped presentation of a member (display name, avatar,
  progression, achievements, activity) — presentation only, owned data lives in Identity/Gamification.
- **Activity Entry**: A visibility-scoped, event-sourced record of community-relevant activity.
- **Leaderboard**: A ranking by a metric honoring leaderboard visibility/opt-out.
- **Achievement / Quest / Challenge (referenced)**: Defined by Gamification; presented by Community.
- **Community Project**: A proposed evolution with lifecycle, votes, and funding.
- **Proposal**: The initial submission of a community project.
- **Vote**: A free, one-per-active-account expression of support (no Coins).
- **Funding**: A Coins-based contribution to a project, recorded as an Economy transaction; independent
  of votes.
- **Contribution (referenced)**: The community-value metric owned by Gamification.
- **Permission/Visibility/Notification/Economy (referenced)**: Engines this module composes with.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Friends, followers, social graph, DM, likes, and native chat exist in the core Community
  module in 0% of surfaces.
- **SC-002**: Every Active account can vote for free with no minimum level in 100% of cases; non-active
  accounts vote in 0% of cases.
- **SC-003**: Voting costs Coins in 0% of cases and funding counts as a vote in 0% of cases (full
  independence).
- **SC-004**: Funding marks a project as guaranteed to be implemented in 0% of cases; reserved funds
  resolve per published rules as new Economy transactions in 100% of terminal cases.
- **SC-005**: A duplicate vote by the same account on the same project is counted more than once in 0%
  of cases.
- **SC-006**: Community surfaces expose another user's Private data by permission alone in 0% of cases;
  leaderboard opt-out is honored in 100% of cases.
- **SC-007**: Community re-defines achievement/quest/reward logic in 0% of cases (always reflects
  Gamification).
- **SC-008**: Contribution is granted deterministically per Gamification rules in 100% of recognized
  cases; duplicate/farmed Contribution is granted in 0% of cases.
- **SC-009**: Community notifications are produced via the notification engine in 100% of cases (no
  parallel mechanism); recipient preferences/permissions honored in 100% of cases.
- **SC-010**: After a member's account deletion, identifying community presence remains in 0% of cases
  while integrity counts/transactions are preserved non-identifying in 100% of cases.

## Assumptions

- XP, Contribution, Coins, and the definitions/reward logic for achievements/quests/challenges are
  owned by the Gamification spec; Community presents and triggers them.
- The Coins ledger and transaction semantics are owned by the Economy spec; funding records
  transactions there.
- The authorization, privacy/visibility, notification, event/history, and search engines are owned by
  their specs; Community composes with them.
- "Active account" is defined by the Identity & Users spec (only the Active state qualifies).
- The exact project proposal review/decision policy (who accepts/declines, and how votes/funding inform
  it) is administrative policy. (Flagged as OQ-55.)
- Whether challenges are distinct from quests or a sub-type is a Gamification modeling decision referenced
  here. (Flagged as OQ-57.)

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation.

- **OQ-55 (Project decision authority)**: Confirm who decides Accepted/Declined and how votes and
  funding inform (but do not bind) that decision, and whether thresholds exist.
- **OQ-56 (Reserved-funds rules)**: Confirm the standard published rules for reserved funds on
  decline/closure (refund vs consume, partial, deadlines), consistent with the Economy spec.
- **OQ-57 (Quests vs challenges)**: Confirm whether "challenges" are a distinct concept from quests or a
  sub-type/time-boxed variant, so Community presents them correctly (owned by Gamification).
- **OQ-58 (Vote model)**: Confirm the vote model (single up-vote of support vs multi-option/ranked) and
  whether a user may change or retract a vote.
- **OQ-59 (Proposal permission)**: Confirm which roles may propose projects and whether proposals are
  moderated before becoming visible/votable.

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference) and the project
  Constitution (v1.0.0).
- Composes with: `specs/002-identity-users/spec.md` ("active account" eligibility; member identity),
  `specs/003-roles-permissions/spec.md` (gating; propose/vote/fund/moderate permissions),
  `specs/007-events-history/spec.md` (community events, provenance/idempotency),
  `specs/010-notifications/spec.md` (status-change/reminder communications).
- Depends on / references: `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`,
  `ux/UX_PRINCIPLES.md`, `ux/USER_JOURNEYS.md`, `architecture/DATA_MODEL.md`, `architecture/EVENT_MODEL.md`.
- Related specs (not owned here): Gamification (XP/Contribution/Coins, achievements/quests/challenges,
  reward engine, anti-abuse, campaigns), Economy (Coins ledger/transactions), Marketplace (projects as a
  convergence point), the Privacy spec (021) (visibility engine), and a future Chat plugin (out of core scope).
