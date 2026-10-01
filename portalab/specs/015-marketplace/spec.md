# Feature Specification: Marketplace

**Feature Branch**: `015-marketplace`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Detailed functional specification of the Marketplace, including community funding."

## Role of This Document

This is a **detailed feature specification** for the Marketplace — the convergence point where products
(plugins, widgets, statistics, themes, effects, badges, titles, quotas, features, access, community
projects) are published, acquired (free or with Coins, under conditions), owned, activated, refunded,
granted, and revoked; and where **community funding** runs its idea→release lifecycle. It conforms to
and refines the superior reference specification (`specs/001-portal-global-spec/spec.md`) and composes
with Roles & Permissions (`specs/003-roles-permissions/spec.md`), Events & History
(`specs/007-events-history/spec.md`), Notifications (`specs/010-notifications/spec.md`), Community
(`specs/012-community/spec.md`), Gamification & Economy (`specs/013-gamification-economy/spec.md`), and
Campaigns (`specs/014-campaigns/spec.md`), under the project Constitution
(`.specify/memory/constitution.md`, v1.0.0). It draws on `product/PRODUCT_BLUEPRINT.md`,
`product/BUSINESS_RULES.md`, and `architecture/EXTENSIBILITY.md`.

Scope boundary: this spec **owns** the Marketplace surfaces and rules — product catalog/categories,
publication/availability, pricing/conditions, purchase/ownership/activation, purchase history, refunds,
admin grants/revocation, Marketplace audit, and the community-funding lifecycle (as the Marketplace
convergence of Community proposals + Economy funding). It **consumes** the economy ledger (Coins
movements owned by Gamification & Economy), the extension model (plugin/widget/theme activation owned by
the Extension Registry), the authorization/privacy/notification/event engines, and Community's
proposal/vote model. It does **not** re-implement those engines. It chooses no technology and contains
no implementation detail.

### Locked Marketplace & Economy Rules (normative)

- An **already-owned permanent product MUST NOT be purchased twice** (unless explicitly repeatable).
- **Marketplace plugins activate immediately after acquisition** unless explicit configuration is
  required (then shown as needs-configuration until configured).
- **Request quota MAY be sold for Coins; paid request-processing priority MUST NOT exist.**
- **Archived products remain accessible to existing owners.**
- **Coins are virtual/internal, no real-money purchase; refunds are new transactions (never retroactive
  edits); balance never negative.** (Ledger rules owned by Gamification & Economy.)
- **Community funding**: votes are free; funding uses Coins; funds are reserved during the project;
  reject/abandon → refund per defined rules; completion → consume per announced rules; **funding never
  guarantees technical feasibility/implementation.**

**Terminology**: Product = a Marketplace offering; Purchase/Acquisition = obtaining ownership; Grant =
an admin-conferred ownership without purchase; Revocation = removal of access per rules; Campaign = a
themed time-bound operation; Domain Event = a recorded fact.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Browse catalog by category and view product detail/conditions (Priority: P1)

A user browses the Marketplace by category, opens a product detail page, and sees its type, price, and
acquisition conditions (free, Coins, level, achievement, campaign, role, or a combination) and whether
they are eligible.

**Why this priority**: Discovery and clear conditions are the entry point; users must understand what a
product is, what it costs, and whether they qualify before acquiring.

**Independent Test**: Browse categories; open products of several types; confirm each shows type, price,
conditions, ownership status, and an accurate eligibility indication for the current user.

**Acceptance Scenarios**:

1. **Given** published products across categories, **When** a user browses, **Then** products are listed
   by category with type and price/conditions visible.
2. **Given** a product detail page, **When** viewed, **Then** it shows the product type, price,
   acquisition conditions, and the user's ownership/eligibility status.
3. **Given** a product the user is ineligible for, **When** viewed, **Then** the unmet condition(s) are
   clearly indicated (e.g., "requires Level X", "requires achievement Y").

### User Story 2 - Acquire a product with conditions (free / Coins / level / achievement / campaign / role / combination) (Priority: P1)

A user acquires a product when they meet its conditions; a Coins price deducts via a traceable
transaction; condition combinations (e.g., Coins + minimum level) are all required.

**Why this priority**: Conditional acquisition is the core Marketplace mechanic and ties directly to the
economy and gamification rules.

**Independent Test**: Acquire a free product, a Coins-priced product, and a product with a combined
condition (e.g., Coins + level + role); confirm each succeeds only when all conditions are met and that
Coins deductions are recorded as transactions.

**Acceptance Scenarios**:

1. **Given** a free product the user is eligible for, **When** acquired, **Then** ownership is granted
   with no Coins movement and a `marketplace.purchase`/unlock event is recorded.
2. **Given** a Coins-priced product and sufficient Coins, **When** purchased, **Then** Coins are deducted
   via a traceable economy transaction and ownership is granted.
3. **Given** a product with combined conditions (e.g., Coins + Level + role/achievement/campaign),
   **When** the user meets all, **Then** acquisition succeeds; **When** any condition is unmet, **Then**
   it is refused with the unmet condition named.
4. **Given** insufficient Coins, **When** purchase is attempted, **Then** it is refused and the balance
   never goes negative.

### User Story 3 - Ownership: no double purchase; archived keeps access (Priority: P1)

A product already owned (permanent) cannot be purchased again unless explicitly repeatable; if a product
is archived, existing owners keep access while it is no longer newly purchasable.

**Why this priority**: These are locked rules protecting users from double-charging and preserving
earned/paid access.

**Independent Test**: Purchase a permanent product; attempt to buy it again (refused); archive a product
and confirm an existing owner still has access while new purchases are blocked.

**Acceptance Scenarios**:

1. **Given** an owned permanent product, **When** the user tries to purchase it again, **Then** it is
   refused (no double purchase) unless the product is explicitly repeatable.
2. **Given** a repeatable product, **When** purchased again, **Then** a new acquisition is recorded as
   defined by the product.
3. **Given** an archived product, **When** an existing owner uses it, **Then** access is retained; **When**
   a non-owner tries to acquire it, **Then** it is not available for new purchase.

### User Story 4 - Immediate plugin activation (unless configuration required) (Priority: P1)

When a user acquires a Marketplace plugin (or widget/theme), it activates immediately unless explicit
configuration is required, in which case it is shown as needs-configuration until configured.

**Why this priority**: Immediate activation is a locked rule and the expected acquisition experience;
the configuration exception must be handled cleanly.

**Independent Test**: Acquire a plugin requiring no configuration and confirm it is active immediately;
acquire one requiring configuration and confirm it is owned but inactive until configured, then
activates.

**Acceptance Scenarios**:

1. **Given** a Marketplace plugin requiring no configuration, **When** acquired, **Then** it activates
   immediately and integrates via the extension model.
2. **Given** a plugin requiring explicit configuration, **When** acquired, **Then** it is owned but shown
   as needs-configuration and activates once configured.
3. **Given** activation via the extension model, **When** it occurs, **Then** it follows extension
   compatibility checks and does not, on failure, break unrelated functions.

### User Story 5 - Purchase history, refunds, grants, revocation, audit (Priority: P1)

A user sees their purchase history; refunds are issued per rules as new transactions; admins can grant
products without purchase and revoke access per rules; all sensitive actions are audited.

**Why this priority**: History/refunds/grants/revocation/audit are explicit and carry economic and trust
weight; refunds must follow the append-only ledger rule.

**Independent Test**: View purchase history; issue a refund (confirm a new transaction, not an edit);
admin-grant a product (confirm ownership without purchase); revoke access (confirm per-rule removal); and
confirm each sensitive action is audited.

**Acceptance Scenarios**:

1. **Given** past acquisitions, **When** the user views history, **Then** each acquisition (free/Coins/
   grant), its conditions, and status are shown.
2. **Given** a refundable purchase, **When** refunded, **Then** Coins are returned via a NEW economy
   transaction referencing the original (never a retroactive edit) and ownership adjusts per rules.
3. **Given** admin permission, **When** an admin grants a product, **Then** ownership is conferred without
   a purchase, marked as a grant, and audited.
4. **Given** admin permission and a defined rule, **When** access is revoked, **Then** it is removed per
   the rule, recorded, and audited; the user is informed per notification preferences.

### User Story 6 - Seerr-style quota products with no paid priority (Priority: P1)

A user can buy additional request quota with Coins; however, no product or payment ever grants faster or
prioritized request processing — paid processing priority does not exist.

**Why this priority**: This is an explicit, locked fairness rule; selling quota is allowed, selling
priority is forbidden.

**Independent Test**: Purchase additional request quota with Coins and confirm the quota increases;
confirm there is no product, option, or mechanism that grants processing priority for payment.

**Acceptance Scenarios**:

1. **Given** a quota product, **When** purchased with Coins, **Then** the user's request quota increases
   via a traceable transaction.
2. **Given** the Marketplace, **When** inspected, **Then** no product or option grants paid
   request-processing priority (it does not exist).
3. **Given** quota is consumed, **When** requests are made, **Then** quota limits apply without any
   priority differentiation based on payment.

### User Story 7 - Community funding lifecycle: idea → release (Priority: P1)

A community funding project moves Idea → Proposal → Votes (free) → Funding (Coins, reserved) → Admin
validation → Development → Beta → Release; votes are free, funding reserves Coins, and outcomes resolve
reserved funds per defined rules.

**Why this priority**: This is the explicit, locked community-funding lifecycle at the Marketplace
convergence; it encodes vote/fund independence, reservation, and refund/consume rules.

**Independent Test**: Take a project through the lifecycle; confirm votes are free, funding reserves
Coins (not spent until resolved), admin validation gates development, and reserved funds are refunded on
reject/abandon or consumed on completion per announced rules.

**Acceptance Scenarios**:

1. **Given** an idea, **When** it becomes a proposal, **Then** any active account may vote for free, and
   users may fund it with Coins that are RESERVED (not yet consumed).
2. **Given** a funded proposal, **When** an admin validates it, **Then** it may proceed to Development,
   Beta, and Release; validation is a permissioned, audited decision.
3. **Given** a project is rejected or abandoned, **When** it reaches that terminal state, **Then**
   reserved funds are refunded per the defined rules (as new transactions).
4. **Given** a project is completed, **When** it is released, **Then** reserved funds are consumed per the
   announced rules (as new transactions).
5. **Given** any funding, **When** the project is assessed, **Then** funding never guarantees that
   implementation is technically possible.

### User Story 8 - Marketplace administration: publish & manage products (Priority: P2)

An admin publishes and manages products — setting type, category, price, conditions, availability,
repeatability, and archive state — as permissioned, audited actions.

**Why this priority**: Administration governs the whole Marketplace; it must be controlled and auditable.

**Independent Test**: As an admin, publish a product with conditions, change its availability, archive
it, and confirm each action is permissioned and audited and reflected in the catalog.

**Acceptance Scenarios**:

1. **Given** admin permission, **When** a product is published with type/category/price/conditions,
   **Then** it appears in the catalog per its availability and the action is audited.
2. **Given** a published product, **When** its availability/price/conditions change, **Then** changes are
   versioned/audited and historical purchases are not reinterpreted.
3. **Given** a product is archived, **When** done, **Then** existing owners keep access and new purchases
   are blocked.

### Edge Cases

- **Double purchase of a permanent product**: Refused; the owned product cannot be bought again unless
  explicitly repeatable.
- **Insufficient Coins**: Purchase/funding refused; balance never goes negative.
- **Combined conditions partially met**: Acquisition refused with the specific unmet condition(s) named;
  no partial ownership.
- **Condition changes after purchase**: Historical purchases keep their recorded conditions/price;
  changing a product's conditions does not retroactively revoke prior owners (archive/revocation rules
  govern access).
- **Archived product**: Existing owners retain access; new purchases blocked; refunds still follow rules
  where applicable.
- **Plugin activation failure**: Isolated via the extension model; a failing plugin does not break
  unrelated functions; ownership is retained and the user is informed.
- **Refund after partial use**: Refund follows the product's defined refund rule; it is a new transaction
  referencing the original, never an edit; non-refundable products are marked as such before purchase.
- **Grant then revoke**: A granted product can be revoked per rules; both are audited; revocation does
  not rewrite the grant's history.
- **Funding reserved then project changes**: Reserved funds are not spent until resolution; on reject/
  abandon they refund, on completion they consume — per the announced rules, as new transactions.
- **Vote/fund conflation**: Voting is free and never costs Coins; funding never counts as a vote (per
  Community); the Marketplace preserves this separation.
- **Paid priority attempt**: There is no mechanism to purchase request-processing priority; quota ≠
  priority.
- **Campaign-conditioned product outside campaign**: A product requiring an active campaign is not
  acquirable when the campaign is inactive.
- **Account deletion with owned products / reserved funding**: Ownership and reserved funds resolve per
  the deletion lifecycle and funding rules; remaining Coins are destroyed; history anonymized but
  integrity-preserving.

## Requirements *(mandatory)*

### Functional Requirements

#### Catalog, Categories, Product Types
- **FR-001**: The Marketplace MUST present products organized by category, each with a product type:
  plugin, widget, statistic, theme, effect, badge, title, quota, feature, access, or community project.
- **FR-002**: A product detail MUST show type, price, acquisition conditions, and the current user's
  ownership/eligibility status.
- **FR-003**: Products MUST be searchable/discoverable per the user's permissions (integrating with
  Global Search and the shell).

#### Pricing & Conditions
- **FR-004**: A product MUST support acquisition conditions: free, Coins price, minimum level, required
  achievement, active campaign, required role, or a combination (all combined conditions required).
- **FR-005**: Eligibility MUST be evaluated server-side (deny-by-default); unmet conditions MUST be named
  to the user; acquisition MUST be refused unless all conditions are met.
- **FR-006**: A Coins price MUST be charged via a traceable economy transaction (owned by Gamification &
  Economy); the balance MUST never go negative.

#### Publication & Availability
- **FR-007**: Admins MUST be able to publish products with type, category, price, conditions,
  availability, and repeatability; publication/management MUST be permissioned and audited.
- **FR-008**: Availability states MUST include at least available, archived (existing owners keep access;
  no new purchases), and unavailable; changes MUST be versioned/audited.
- **FR-009**: Changing a product's price/conditions MUST NOT reinterpret or rewrite historical purchases.

#### Purchase, Ownership, Activation
- **FR-010**: Acquiring a product MUST confer ownership and record a `marketplace.purchase`/
  `marketplace.unlock` event; free and Coins acquisitions MUST both be recorded.
- **FR-011**: An already-owned permanent product MUST NOT be purchasable again unless explicitly
  repeatable; repeatable products MUST record each acquisition as defined.
- **FR-012**: A Marketplace plugin/widget/theme MUST activate immediately on acquisition unless explicit
  configuration is required, in which case it MUST be owned-but-inactive (needs-configuration) until
  configured.
- **FR-013**: Activation MUST occur via the extension model (compatibility checks apply) and a failure
  MUST be isolated so it does not break unrelated functions.

#### Purchase History, Refunds, Grants, Revocation, Audit
- **FR-014**: Users MUST be able to view their purchase/acquisition history with conditions, price, and
  status.
- **FR-015**: Refunds MUST follow the product's defined refund rule and MUST be issued as NEW economy
  transactions referencing the original (never retroactive edits); non-refundable products MUST be marked
  before purchase.
- **FR-016**: Admins MUST be able to grant a product without purchase (marked as a grant) and to revoke
  access per defined rules; both MUST be audited.
- **FR-017**: Revocation MUST remove access per rule without rewriting the acquisition/grant history and
  MUST inform the user per notification preferences.
- **FR-018**: Every sensitive Marketplace action (publish, price/condition change, refund, grant,
  revocation, archive) MUST produce an audit entry (actor, action, timestamp, context, result).

#### Quota Products & No Paid Priority (Seerr)
- **FR-019**: The Marketplace MUST support selling additional request quota for Coins, increasing the
  buyer's quota via a traceable transaction.
- **FR-020**: No product, option, or mechanism MUST grant paid request-processing priority; processing
  priority based on payment MUST NOT exist.

#### Community Funding Lifecycle
- **FR-021**: The Marketplace MUST support the community-funding lifecycle: Idea → Proposal → Votes →
  Funding → Admin validation → Development → Beta → Release.
- **FR-022**: Votes MUST be free and available to every active account (per Community); funding MUST use
  Coins and MUST be independent of voting.
- **FR-023**: Funding MUST reserve Coins (reserved, not consumed) for the duration of the project,
  recorded as reservation transactions.
- **FR-024**: Admin validation MUST be a permissioned, audited gate before Development; votes/funding
  inform but MUST NOT bind the decision.
- **FR-025**: On reject/abandon, reserved funds MUST be refunded per the defined rules (new
  transactions); on completion/release, reserved funds MUST be consumed per the announced rules (new
  transactions).
- **FR-026**: Funding MUST NOT guarantee that implementation is technically possible; this MUST be
  communicated at funding time.

#### Cross-Cutting (permissions, privacy, events, economy)
- **FR-027**: All Marketplace operations MUST be gated by the authorization engine (deny-by-default,
  server-side) and MUST respect privacy; ownership/history MUST NOT expose others' private data.
- **FR-028**: All Coin movements (purchase, refund, funding reservation, consumption, destruction) MUST
  be transactions in the economy ledger under its append-only rules (owned by Gamification & Economy).
- **FR-029**: Marketplace domain events (`marketplace.purchase`, `marketplace.unlock`,
  `marketplace.refund`, `project.*` funding events) MUST be emitted with `occurred_at` distinct from
  `received_at`; consumers MUST be idempotent (no double purchase/charge on duplicate delivery).
- **FR-030**: Marketplace notifications (purchase confirmation, funding status, revocation, project
  status) MUST be produced only via the notification engine, respecting preferences/permissions.
- **FR-031**: On final account deletion, owned products and reserved funding MUST resolve per the
  deletion lifecycle and funding rules; remaining Coins MUST be destroyed and history anonymized while
  preserving integrity.

### Product Availability State Model

**States**: Draft, Published/Available, Archived (existing owners keep access, no new purchase),
Unavailable (temporarily not purchasable).

**Invariants**:
- Archived never removes access from existing owners.
- Publication/availability/price/condition changes are versioned/audited and never reinterpret
  historical purchases.
- A permanent owned product is not re-purchasable unless explicitly repeatable.

### Community Funding Lifecycle Model

**Stages**: Idea → Proposal → Voting (free) + Funding (Coins reserved) → Admin Validation →
Development → Beta → Release; terminal off-ramps: Rejected / Abandoned.

**Fund handling**:
- Funding **reserves** Coins (reservation transaction) — not consumed during the project.
- **Rejected/Abandoned** → reserved funds **refunded** per defined rules (new transactions).
- **Release (completed)** → reserved funds **consumed** per announced rules (new transactions).
- Funding never guarantees technical feasibility.

**Invariants**:
- Votes are free; funding is separate and Coins-based (per Community).
- Reserved funds are only refunded or consumed per published rules — never silently.
- Admin validation is a permissioned, audited gate that votes/funding inform but do not bind.

### Marketplace-Related Domain Events

Names aligned with the Event Model; each carries actor/context, product/project reference, version,
metadata.

- `marketplace.purchase`, `marketplace.unlock`, `marketplace.refund`
- `marketplace.product_published`, `marketplace.product_archived`, `marketplace.product_updated`
- `marketplace.grant`, `marketplace.revocation`
- `project.created`, `project.vote_added`, `project.funding_added`, `project.status_changed`
  (funding lifecycle; shared with Community)

### Key Entities

- **MarketplaceProduct**: An offering with type, category, price, conditions, availability,
  repeatability, refund rule, and version.
- **Product Type**: plugin / widget / statistic / theme / effect / badge / title / quota / feature /
  access / community project.
- **Acquisition Condition**: free / Coins / level / achievement / campaign / role / combination
  (all combined conditions required).
- **Purchase / Acquisition**: An ownership record (free, Coins, or grant) with conditions/price at time.
- **Ownership**: A user's entitlement to a product (permanent or repeatable), including archived-access.
- **Refund**: A new economy transaction reversing a purchase per the refund rule (never an edit).
- **Grant / Revocation**: Admin-conferred ownership / rule-based access removal (both audited).
- **Quota Product**: A product increasing request quota; never priority.
- **Community Funding Project**: A proposal with votes (free) and reserved Coins funding across the
  idea→release lifecycle.
- **Funding Reservation**: Reserved Coins held during a project, later refunded or consumed per rules.
- **Economy Transaction / Permission / Notification / Extension (referenced)**: Engines composed with.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An already-owned permanent product is purchasable again in 0% of cases (unless explicitly
  repeatable).
- **SC-002**: Acquisition succeeds with any unmet condition in 0% of cases; combined conditions require
  all to be met in 100% of cases.
- **SC-003**: A Coins purchase/funding drives the balance negative in 0% of cases; 100% of Coin movements
  are recorded as traceable transactions.
- **SC-004**: A Marketplace plugin requiring no configuration is active immediately in 100% of cases;
  one requiring configuration activates before configuration in 0% of cases.
- **SC-005**: Archived products remain accessible to existing owners in 100% of cases and are newly
  purchasable in 0% of cases.
- **SC-006**: Refunds are implemented as new transactions referencing the original in 100% of cases and
  as retroactive edits in 0% of cases.
- **SC-007**: A mechanism granting paid request-processing priority exists in 0% of cases; quota
  purchases increase quota in 100% of valid cases.
- **SC-008**: In community funding, votes cost Coins in 0% of cases; reserved funds are refunded (reject/
  abandon) or consumed (release) strictly per defined rules in 100% of terminal cases.
- **SC-009**: Funding is represented as guaranteeing technical implementation in 0% of cases.
- **SC-010**: 100% of sensitive Marketplace actions (publish, price/condition change, refund, grant,
  revocation, archive, admin validation) produce an audit entry.

## Assumptions

- The Coins ledger, transaction types (including reservation/consumption/refund/destruction), and
  anti-abuse are owned by Gamification & Economy; the Marketplace records movements there.
- Plugin/widget/theme activation and compatibility are owned by the Extension Registry; the Marketplace
  triggers activation via that model.
- Community's proposal/vote model and "active account" eligibility are owned by Community/Identity; the
  Marketplace is the funding convergence surface.
- Campaign conditions reference active campaigns owned by the Campaigns spec.
- The exact refund rules per product type, and the funding refund/consume formulas, are configurable
  product/project policy. (Flagged as OQ-70/OQ-71.)
- Quota semantics (what a "request" is, per which connected service like Seerr) are defined by the
  relevant service/connector; the Marketplace only sells quota, never priority. (Flagged as OQ-72.)

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation.

- **OQ-70 (Refund rules)**: Confirm the default refund policy per product type (refundable window,
  partial vs full, non-refundable categories) consistent with the economy ledger.
- **OQ-71 (Funding refund/consume formulas)**: Confirm how reserved funds are refunded on reject/abandon
  (full vs fee) and consumed on release (all vs milestone-based), and who defines the per-project rules.
- **OQ-72 (Quota semantics)**: Confirm what request quota applies to (which services, e.g., Seerr), how
  quota is measured/reset, and its interaction with campaigns.
- **OQ-73 (Revocation conditions)**: Confirm the legitimate grounds/rules for revoking access to an owned
  product (e.g., abuse, admin grant expiry) so revocation is never arbitrary.
- **OQ-74 (Combined-condition semantics)**: Confirm whether combined conditions are strictly AND, or
  support OR/any-of groupings, for product eligibility.

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference) and the project
  Constitution (v1.0.0).
- Composes with: `specs/003-roles-permissions/spec.md` (`marketplace.manage`/`economy.manage`; gating/
  audit), `specs/007-events-history/spec.md` (marketplace/funding events, idempotency),
  `specs/010-notifications/spec.md` (purchase/funding/revocation communications), `specs/012-community/spec.md`
  (proposals, free voting, funding independence), `specs/013-gamification-economy/spec.md` (Coins ledger,
  transactions, conditions like level/achievement), and `specs/014-campaigns/spec.md` (campaign
  conditions).
- Depends on / references: `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`,
  `architecture/EXTENSIBILITY.md`, `architecture/EVENT_MODEL.md`, `architecture/DATA_MODEL.md`.
- Related specs (not owned here): the Extension Registry (plugin/widget/theme activation), Gamification &
  Economy (ledger/conditions), Community (proposals/votes), the Privacy spec (021) (visibility), and the relevant
  service/connector specs for quota (e.g., Seerr-style request services).
