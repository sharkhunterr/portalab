# Feature Specification: Gamification & Economy

**Feature Branch**: `013-gamification-economy`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Detailed functional specification of the Gamification & Economy system."

## Role of This Document

This is a **detailed feature specification** for Gamification & Economy — the engine that defines and
grants the three tracked values (XP, Contribution, Coins), derives Levels, runs achievements/quests/
daily objectives, applies rewards/multipliers/campaign modifiers, enforces anti-abuse, keeps a
traceable economy ledger, and versions its rules. It conforms to and refines the superior reference
specification (`specs/001-portal-global-spec/spec.md`) and composes with Identity & Users
(`specs/002-identity-users/spec.md`), Roles & Permissions (`specs/003-roles-permissions/spec.md`),
Events & History (`specs/007-events-history/spec.md`), Notifications (`specs/010-notifications/spec.md`),
and Community (`specs/012-community/spec.md`), under the project Constitution
(`.specify/memory/constitution.md`, v1.0.0). It draws on `product/PRODUCT_BLUEPRINT.md`,
`product/BUSINESS_RULES.md`, and `architecture/EVENT_MODEL.md`.

Scope boundary: this spec **owns** the reward/economy engine: the three values, Levels, achievements/
quests/daily objectives definitions and granting, reward rules, multipliers and campaign modifiers,
progression, the economy transaction ledger and history, anti-abuse (cooldown/caps/diminishing
returns/anomaly handling), administrative rewards, and rule versioning. It **consumes** the event
backbone (rewards react to domain events), the authorization engine (who may configure rules / grant
manual rewards), and the notification engine (reward/level-up notifications). It **references** Coins
spending surfaces owned elsewhere (Marketplace purchases, Community funding) — those produce economy
transactions governed by this ledger. It chooses no technology and contains no implementation detail.

### The Three Values (normative)

There are **exactly three** tracked values. A **Level** is a derived progression tier, **NOT** a
fourth currency:

- **XP** — progression; accumulates from activity; drives Levels.
- **Contribution** — community value brought by the user; separate from XP.
- **Coins** — internal virtual currency; spendable; strictly non-real-money.

**Levels** are computed from XP (progression tiers); they are never spent, traded, or treated as a
balance. XP, Contribution, and Coins are **separate** and MUST NEVER be conflated or inter-converted
except via explicitly defined, audited rules (if any).

### Locked Economy Rules (normative)

- Coins are **exclusively virtual and internal**; they **cannot** be purchased with real money.
- On **final account deletion**, remaining Coins are **destroyed**.
- Every Coin movement MUST be a **traceable transaction**.
- A historical transaction MUST **never be rewritten** to hide its origin; corrections are new
  transactions (append-only ledger).
- A balance MUST normally never be **negative**.

**Terminology**: Reward = a granted amount of a value per a rule; Multiplier/Modifier = a factor
applied per rule/campaign; Campaign = a themed time-bound operation (the Blueprint's "Event"); Domain
Event = a recorded fact; `occurred_at` = real occurrence time.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Earn XP, Contribution, Coins deterministically from events (Priority: P1)

A user's activity (via domain events) deterministically grants XP, Contribution, and/or Coins per the
active reward rules; the three values are tracked separately and each Coin grant is a traceable
transaction.

**Why this priority**: Deterministic, separate, traceable granting of the three values is the core of
the whole system; everything else builds on it.

**Independent Test**: Emit a reward-producing event; confirm XP/Contribution/Coins are granted per the
rule, tracked separately, with a Coin transaction recorded; re-emit the same event and confirm no
double grant (idempotent).

**Acceptance Scenarios**:

1. **Given** a reward rule for an event type, **When** the event occurs, **Then** the specified
   XP/Contribution/Coins are granted deterministically and tracked in their separate balances.
2. **Given** a Coin grant, **When** it happens, **Then** a traceable economy transaction is recorded
   (actor/source/amount/reason/rule-version/timestamp).
3. **Given** duplicate delivery of the same event, **When** processed, **Then** the reward is granted
   once (idempotent; no double XP/Contribution/Coins).
4. **Given** XP, Contribution, and Coins, **When** granted, **Then** they remain separate and are not
   inter-converted except by an explicit audited rule.

### User Story 2 - Levels derived from XP (not a currency) (Priority: P1)

As a user accumulates XP, their Level rises per the progression curve; Levels are read-only derived
tiers, never spent or traded.

**Why this priority**: The locked rule "Level is derived progression, not a fourth currency" must be
structurally enforced.

**Independent Test**: Grant XP across a Level threshold; confirm the Level increases, a level-up event
is produced, and that the Level cannot be spent/transferred or treated as a balance.

**Acceptance Scenarios**:

1. **Given** XP crossing a Level threshold, **When** evaluated, **Then** the Level increases and a
   `user.level_up` event is produced.
2. **Given** a Level, **When** any spend/transfer is attempted on it, **Then** it is impossible (Level
   is not a currency/balance).
3. **Given** the progression curve, **When** XP changes, **Then** the Level is always a deterministic
   function of XP under the rule version in force.

### User Story 3 - Achievements, quests, daily objectives (Priority: P1)

Users unlock achievements, complete quests, and fulfill daily objectives; each grants rewards per its
rule, exactly once where it is one-time, within anti-abuse limits.

**Why this priority**: These are the primary engagement mechanics and a major reward source; duplicate
unlocks must be prevented.

**Independent Test**: Satisfy an achievement condition, complete a quest, and complete a daily
objective; confirm each unlocks/completes once, grants its reward, and cannot be re-claimed improperly
(dailies reset per their period).

**Acceptance Scenarios**:

1. **Given** an achievement condition met, **When** evaluated, **Then** it unlocks once, grants its
   reward, and emits `achievement.unlocked`; re-meeting the condition does not re-grant a one-time
   achievement.
2. **Given** a quest completed, **When** evaluated, **Then** it completes, grants its reward, and emits
   `quest.completed`.
3. **Given** a daily objective, **When** completed within its period, **Then** it grants its reward and
   resets per its period (not re-claimable within the same period).

### User Story 4 - Multipliers and campaign modifiers (Priority: P1)

Reward rules can carry multipliers, and overlapping campaigns can apply modifiers; the combined effect
is deterministic, duplicate rewards are prevented, and anti-farming limits still apply.

**Why this priority**: Multipliers/campaigns are explicit and the locked rule requires deterministic
combination of overlapping modifiers without duplicate rewards.

**Independent Test**: Apply a base rule, a multiplier, and two overlapping campaigns; confirm the
resulting grant is deterministic per the configured combination rule, with no duplicate reward and
anti-farming still enforced.

**Acceptance Scenarios**:

1. **Given** a base reward and a multiplier, **When** granted, **Then** the result equals the
   deterministically combined amount under the active rule version.
2. **Given** multiple overlapping campaigns with modifiers, **When** a reward is granted, **Then**
   modifiers combine per the configured deterministic rule (no ambiguity, no duplicate reward).
3. **Given** campaign modifiers, **When** applied, **Then** anti-farming caps/cooldowns/diminishing
   returns still apply.

### User Story 5 - Anti-abuse: cooldown, caps, diminishing returns, anomalies (Priority: P1)

The engine enforces anti-abuse: cooldowns between repeated grants, caps per period, diminishing returns
on repetition, and anomaly detection/handling — preventing farming while keeping legitimate rewards.

**Why this priority**: Anti-abuse is explicit and essential to a fair, trustworthy economy; without it,
XP/Contribution/Coins are meaningless.

**Independent Test**: Repeatedly trigger a reward; confirm cooldown blocks too-frequent grants, a cap
limits per-period totals, diminishing returns reduce repeated-grant value, and an anomalous pattern is
flagged/handled per policy — while a normal pattern is unaffected.

**Acceptance Scenarios**:

1. **Given** a cooldown on a reward, **When** it is triggered again within the cooldown, **Then** the
   repeat grant is withheld or reduced per rule.
2. **Given** a per-period cap, **When** the cap is reached, **Then** further grants in that period are
   withheld.
3. **Given** diminishing returns, **When** the same reward repeats, **Then** each repeat grants less per
   the configured curve.
4. **Given** an anomalous pattern (e.g., implausible rate), **When** detected, **Then** it is flagged/
   handled per policy and recorded, without silently corrupting balances.

### User Story 6 - Traceable, append-only economy transactions (Priority: P1)

Every Coin movement is a transaction in an append-only ledger; balances derive from the ledger;
corrections and refunds are new transactions; a historical transaction is never rewritten to hide its
origin.

**Why this priority**: These are locked economy-integrity rules with the highest trust weight.

**Independent Test**: Perform grants, a spend, a refund, and a manual correction; confirm each is a
distinct transaction, that the balance equals the ledger sum, and that no prior transaction was edited
(refund/correction are new entries referencing the original).

**Acceptance Scenarios**:

1. **Given** any Coin movement (grant, spend, refund, correction), **When** it occurs, **Then** it is
   recorded as a new, traceable transaction with origin/reason/rule-version.
2. **Given** a refund or correction, **When** applied, **Then** it is a new transaction referencing the
   original; the original is never rewritten or deleted.
3. **Given** a balance, **When** computed, **Then** it equals the ledger and never goes negative (a
   spend exceeding balance is refused).

### User Story 7 - Administrative rewards and rule versioning (Priority: P1)

An authorized admin can grant manual rewards (marked and audited); reward/economy rules are versioned
so that changing a rule never reinterprets historical grants/transactions.

**Why this priority**: Manual rewards and rule versioning are explicit; the locked rule "historical
rules/transactions are not rewritten" depends on versioning.

**Independent Test**: Grant a manual reward (confirm it is marked manual and audited); change a reward
rule and confirm new grants use the new version while historical grants retain their original version/
meaning.

**Acceptance Scenarios**:

1. **Given** admin permission, **When** a manual reward is granted, **Then** it is marked as manual,
   attributed to the admin, audited, and recorded as a transaction (for Coins).
2. **Given** a reward rule change, **When** published as a new version, **Then** subsequent grants use
   the new version while historical grants remain bound to the version in force when they occurred.
3. **Given** historical data, **When** a new rule is active, **Then** past grants/transactions are not
   reinterpreted or rewritten.

### User Story 8 - Final account deletion destroys remaining Coins (Priority: P1)

When an account is finally deleted, its remaining Coins are destroyed via a recorded transaction, while
the historical ledger integrity is preserved in anonymized form.

**Why this priority**: A locked rule with privacy and integrity implications; it ties the economy to
the deletion lifecycle.

**Independent Test**: Delete an account holding Coins; confirm remaining Coins are destroyed via a
recorded destruction transaction, the user is no longer identifiable, and prior transactions remain for
integrity in anonymized form.

**Acceptance Scenarios**:

1. **Given** final account deletion with remaining Coins, **When** it completes, **Then** the Coins are
   destroyed via a recorded destruction transaction.
2. **Given** deletion, **When** it completes, **Then** historical transactions are preserved for
   integrity but anonymized (no longer identifying the person).
3. **Given** destroyed Coins, **When** anything references them later, **Then** there is no real-value
   refund (Coins are virtual-only).

### User Story 9 - Leaderboards and progression display (Priority: P2)

Users see their progression (XP/Level, Contribution, Coins) and leaderboards by metric, honoring
visibility; the engine provides the authoritative values that Community/Dashboard present.

**Why this priority**: Progression visibility drives engagement; Gamification owns the values while
Community/Dashboard present them.

**Independent Test**: View progression and a leaderboard; confirm values match the engine's
authoritative state, respect leaderboard visibility/opt-out, and expose no private data by permission
alone.

**Acceptance Scenarios**:

1. **Given** a user's values, **When** progression is viewed, **Then** XP/Level, Contribution, and Coins
   are shown accurately and separately.
2. **Given** leaderboards, **When** viewed, **Then** they rank by the metric honoring leaderboard
   visibility/opt-out and expose no private data by permission alone.

### Edge Cases

- **Duplicate/late reward events**: Rewards are idempotent per `occurred_at`/dedup; a redelivered or
  late event does not double-grant.
- **Overlapping campaigns**: Modifiers combine by the configured deterministic rule; never ambiguous,
  never a duplicate reward for the same occurrence.
- **Spend exceeding balance**: Refused; balance never goes negative; no partial corruption.
- **Refund after rule change**: The refund is a new transaction referencing the original and uses the
  original's recorded values/version; it does not reinterpret history.
- **Manual correction**: Marked, audited, and recorded as a new transaction; the erroneous original is
  never edited/deleted (only corrected forward).
- **Diminishing returns + cap + cooldown interaction**: The combination is deterministic and
  documented; order of application is defined so results are reproducible.
- **Anomalous earning pattern**: Flagged/handled per policy (e.g., withhold, review) and recorded;
  legitimate activity is unaffected; balances are never silently altered without a transaction.
- **Level recomputation after XP correction**: If XP is corrected (via a new transaction/record), Level
  recomputes deterministically; it is never spent, so no "Level refund" exists.
- **Account deletion with pending rewards**: Pending/undelivered rewards resolve per policy before/at
  destruction; remaining Coins destroyed via transaction; integrity ledger anonymized.
- **Rule version missing for a historical grant**: Impossible by design — every grant records the rule
  version in force; reconstruction uses it.
- **Reconstruction/replay**: Rebuilding derived state (e.g., totals) uses historical rule versions and
  does not re-grant one-off rewards or re-emit notifications (consistent with Events & History).
- **Real-money purchase attempt**: There is no mechanism to buy Coins with real money; any such attempt
  is impossible/refused.
- **Contribution farming via community**: Anti-abuse applies to Contribution exactly as to XP/Coins
  (cooldown/caps/diminishing/anomaly).

## Requirements *(mandatory)*

### Functional Requirements

#### The Three Values & Levels
- **FR-001**: The system MUST track exactly three separate values — XP, Contribution, Coins — and MUST
  NOT conflate or inter-convert them except via an explicitly defined, audited rule.
- **FR-002**: The system MUST derive Level from XP as a deterministic progression tier; Level MUST NOT
  be spendable, transferable, or treated as a balance/currency.
- **FR-003**: Crossing a Level threshold MUST produce a `user.level_up` event; Level MUST always be a
  deterministic function of XP under the active rule version.

#### Reward Granting (deterministic, idempotent)
- **FR-004**: Reward rules MUST grant XP/Contribution/Coins deterministically in response to defined
  triggers (domain events, achievements, quests, daily objectives, manual grants).
- **FR-005**: Reward granting MUST be idempotent: duplicate/late delivery of the same triggering
  occurrence MUST NOT double-grant (using `occurred_at`/dedup per Events & History).
- **FR-006**: Every Coin grant MUST record a traceable economy transaction (actor/source, amount,
  reason, rule version, timestamp).

#### Achievements, Quests, Daily Objectives
- **FR-007**: The system MUST support achievements that unlock once (for one-time achievements) when
  their condition is met, granting their reward and emitting `achievement.unlocked`.
- **FR-008**: The system MUST support quests that complete and grant rewards, emitting `quest.completed`.
- **FR-009**: The system MUST support daily objectives that grant rewards within their period and reset
  per period, not re-claimable within the same period.
- **FR-010**: Duplicate rewards for achievements/quests/daily objectives MUST be prevented.

#### Multipliers & Campaign Modifiers
- **FR-011**: Reward rules MUST support multipliers, and campaigns MUST support modifiers (and may
  define their own achievements/quests/notifications) over a time window.
- **FR-012**: Overlapping campaigns/modifiers MUST combine via a configured deterministic rule with a
  defined order of application; the result MUST be reproducible and never ambiguous.
- **FR-013**: Multipliers/modifiers MUST NOT bypass anti-abuse (caps/cooldowns/diminishing returns) and
  MUST NOT produce duplicate rewards for the same occurrence.

#### Anti-Abuse (cooldown, caps, diminishing returns, anomalies)
- **FR-014**: The system MUST enforce cooldowns that withhold or reduce too-frequent repeat grants.
- **FR-015**: The system MUST enforce per-period caps that withhold grants beyond the cap.
- **FR-016**: The system MUST support diminishing returns that reduce the value of repeated grants per a
  configured curve.
- **FR-017**: The system MUST detect and handle anomalous earning patterns per policy (e.g., withhold/
  review/flag), recording the handling and never silently altering balances without a transaction.
- **FR-018**: Anti-abuse MUST apply equally to XP, Contribution, and Coins where relevant, and the
  combined effect of cooldown/cap/diminishing MUST be deterministic and documented.

#### Economy Ledger (traceable, append-only, non-negative)
- **FR-019**: Every Coin movement (grant, spend, refund, correction, destruction) MUST be a new,
  traceable transaction in an append-only ledger.
- **FR-020**: A historical transaction MUST NEVER be rewritten, edited, or deleted to hide/alter its
  origin; corrections and refunds MUST be new transactions referencing the original.
- **FR-021**: A balance MUST be derivable from the ledger and MUST normally never be negative; a spend
  exceeding balance MUST be refused.
- **FR-022**: Coins MUST be exclusively virtual and internal and MUST NOT be purchasable with real
  money; no real-money purchase mechanism MUST exist.
- **FR-023**: Coin-spending surfaces owned elsewhere (Marketplace purchases, Community funding) MUST
  record their movements as transactions in this ledger under the same rules.

#### Administrative Rewards & Rule Versioning
- **FR-024**: Authorized admins MUST be able to grant manual rewards; manual rewards MUST be marked as
  manual, attributed, audited, and (for Coins) recorded as transactions.
- **FR-025**: Reward/economy rules MUST be versioned; a rule change MUST be published as a new version
  used for subsequent grants only.
- **FR-026**: Historical grants/transactions MUST remain bound to the rule version in force when they
  occurred and MUST NOT be reinterpreted by a new rule.
- **FR-027**: Configuring reward/economy rules, multipliers, campaigns, and granting manual rewards MUST
  be permission-gated sensitive actions, confirmed where appropriate and audited.

#### Final Deletion
- **FR-028**: On final account deletion, remaining Coins MUST be destroyed via a recorded destruction
  transaction (no real-value refund).
- **FR-029**: After deletion, historical transactions MUST be preserved for integrity in anonymized form
  (no longer identifying the person), consistent with the privacy/deletion lifecycle.

#### Progression, Leaderboards, History
- **FR-030**: The system MUST expose authoritative progression values (XP/Level, Contribution, Coins)
  that Community/Dashboard present, separately and accurately.
- **FR-031**: The system MUST provide leaderboards by metric honoring leaderboard visibility/opt-out,
  exposing no private data by permission alone.
- **FR-032**: Gamification/economy actions MUST emit domain events (`reward.granted`,
  `achievement.unlocked`, `quest.completed`, `user.level_up`, `marketplace.*`/funding transactions as
  applicable) with `occurred_at` distinct from `received_at`; consumers MUST be idempotent.
- **FR-033**: Reward/level-up/achievement notifications MUST be produced only via the notification
  engine, respecting recipient preferences/permissions (no parallel mechanism).
- **FR-034**: Progression/economy history MUST be retained with provenance; historized data MUST NOT be
  automatically public and MUST follow privacy rules.

#### Resilience & Reconstruction
- **FR-035**: Reconstruction of derived totals MUST use historical rule versions, be deterministic, and
  MUST NOT re-grant one-off rewards or re-emit notifications (consistent with Events & History).
- **FR-036**: A failure in gamification/economy processing MUST NOT corrupt balances (transactions are
  atomic/traceable) and MUST NOT break unrelated portal functions.

### Economy Transaction Model

**Transaction types**: grant, spend, refund, correction, destruction.

**Each transaction records (at least)**: id, account (or anonymized subject), value type (always Coins
for the ledger; XP/Contribution tracked analogously), amount (signed), reason/source, originating
rule + rule version, related event/reference, actor (system/user/admin), `occurred_at`, `received_at`.

**Invariants**:
- Append-only: transactions are never edited or deleted.
- Refund/correction = new transaction referencing the original (origin never hidden).
- Balance = deterministic sum of the ledger; never negative.
- Destruction at deletion is itself a recorded transaction.
- XP and Contribution grants are likewise recorded as traceable, versioned entries (same append-only
  discipline), even though they are not "currency" spent like Coins.

### Value & Reward Model

- **XP**: accumulates; drives Level via a versioned progression curve; never spent.
- **Contribution**: accumulates to recognize community value; never a currency; anti-abuse applies.
- **Coins**: spendable internal currency; append-only ledger; never real money; destroyed at deletion.
- **Level**: derived from XP (read-only tier); not a balance.
- **Reward rule (versioned)**: maps a trigger to amounts of XP/Contribution/Coins, with optional
  multiplier, cooldown, cap, diminishing-returns curve, and campaign modifiers.

### Gamification/Economy Domain Events

Names aligned with the Event Model; each carries actor/context, subject reference, rule version,
metadata, version.

- `reward.granted`
- `achievement.unlocked`
- `quest.completed`
- `user.level_up`
- `economy.transaction_recorded` (grant/spend/refund/correction/destruction)
- `campaign.started` / `campaign.ended` (modifier window; the Blueprint's "event")
- `economy.anomaly_flagged`

### Key Entities

- **Value Balance**: A user's current XP, Contribution, and Coins (each separate; Coins derived from
  the ledger).
- **Level**: The derived progression tier from XP.
- **Achievement / Quest / Daily Objective**: Definitions with conditions, reward, one-time/period
  semantics, and reveal rules.
- **Reward Rule (versioned)**: Trigger → reward mapping with multiplier/cooldown/cap/diminishing/
  campaign modifiers, bound to a version.
- **Multiplier / Campaign Modifier**: Factors applied deterministically within a time window.
- **Economy Transaction**: An append-only ledger entry (grant/spend/refund/correction/destruction).
- **Anomaly Record**: A flagged suspicious earning pattern and its handling.
- **Leaderboard (referenced)**: Ranking surface (presented by Community/Dashboard) using engine values.
- **Permission/Notification/Event/Privacy (referenced)**: Engines this system composes with.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The system tracks exactly three values; XP/Contribution/Coins are conflated or
  inter-converted without an explicit audited rule in 0% of cases.
- **SC-002**: Level is spendable/transferable in 0% of cases and is a deterministic function of XP in
  100% of cases.
- **SC-003**: Duplicate/late reward events double-grant in 0% of cases (idempotent).
- **SC-004**: Every Coin movement has a traceable transaction in 100% of cases; a historical
  transaction is rewritten/deleted in 0% of cases (refunds/corrections are new entries in 100%).
- **SC-005**: A balance goes negative in 0% of cases; a spend exceeding balance is accepted in 0% of
  cases.
- **SC-006**: Coins are purchasable with real money in 0% of cases (no mechanism exists).
- **SC-007**: On final deletion, remaining Coins are destroyed via a recorded transaction in 100% of
  cases; the deleted user remains identifiable in the ledger in 0% of cases.
- **SC-008**: Overlapping campaign modifiers produce a non-deterministic or duplicate reward in 0% of
  cases.
- **SC-009**: Anti-abuse (cooldown/cap/diminishing/anomaly) withholds/limits farmed rewards in 100% of
  defined abuse cases while affecting legitimate activity in 0% of defined normal cases.
- **SC-010**: A rule change reinterprets or rewrites historical grants/transactions in 0% of cases
  (historical rule version applied in 100% of reconstructions); manual rewards are marked+audited in
  100% of cases.

## Assumptions

- The specific progression curve, reward amounts, cooldown/cap/diminishing parameters, and campaign
  definitions are configurable administrative data; this spec fixes behavior and guarantees, not fixed
  numbers. (Flagged as OQ-60.)
- Coin-spending surfaces (Marketplace purchases, Community funding) are owned by their specs; they
  record transactions in this ledger under these rules.
- The notification, authorization, privacy, and event/history engines are owned by their specs; this
  system composes with them.
- "Final account deletion" and "active account" semantics are defined by Identity & Users.
- Whether "challenges" (from Community) are quests, daily objectives, or a distinct timed variant is a
  modeling decision owned here. (Flagged as OQ-62.)
- Anomaly handling policy (withhold vs flag-for-review vs auto-reverse) is administrative policy.
  (Flagged as OQ-61.)

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation.

- **OQ-60 (Curves & parameters)**: Confirm the XP→Level progression curve and the baseline parameters
  for cooldowns, caps, and diminishing-returns curves (global vs per-rule), and who configures them.
- **OQ-61 (Anomaly handling policy)**: Confirm how anomalies are handled (withhold grant, flag for
  human review, auto-reverse via correction transaction) and the thresholds that define an anomaly.
- **OQ-62 (Challenges modeling)**: Confirm whether "challenges" are quests, daily objectives, or a
  distinct time-boxed concept, so Community presents them correctly.
- **OQ-63 (Value inter-conversion)**: Confirm whether any XP/Contribution/Coins inter-conversion exists
  at all (default assumption: none) and, if so, the explicit audited rule governing it.
- **OQ-64 (Campaign modifier combination)**: Confirm the exact deterministic combination rule for
  overlapping campaign modifiers (additive, multiplicative, max-wins, priority order) referenced by the
  Campaign/Events spec.

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference) and the project
  Constitution (v1.0.0).
- Composes with: `specs/002-identity-users/spec.md` (active-account, final-deletion Coin destruction),
  `specs/003-roles-permissions/spec.md` (`economy.manage`/gamification permissions; manual-reward gating),
  `specs/007-events-history/spec.md` (reward events, idempotency, reconstruction, rule versioning),
  `specs/010-notifications/spec.md` (reward/level-up notifications), and `specs/012-community/spec.md`
  (Contribution, funding transactions, leaderboards presentation).
- Depends on / references: `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`,
  `architecture/EVENT_MODEL.md`, `architecture/DATA_MODEL.md`.
- Related specs (not owned here): Marketplace (Coin spending, products, refunds), a Campaigns/Events
  spec if separated (modifier definitions), Community (presentation of achievements/quests/leaderboards),
  and the Privacy spec (021) (visibility engine).
