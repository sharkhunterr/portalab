# Feature Specification: Automation / Rules Engine

**Feature Branch**: `019-automations`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Detailed functional specification of the Automation / Rules Engine (WHEN → IF → THEN), transversal but not a full n8n clone."

## Role of This Document

This is a **detailed feature specification** for the Automation / Rules Engine — a transversal
WHEN→IF→THEN reaction system that lets the portal (and authorized users) react to triggers under
conditions by performing authorized actions, with strong safety constraints (permission-bounded,
audited, loop/repeat-protected, timed, auto-suspended on repeated errors). It conforms to and refines
the superior reference specification (`specs/001-portal-global-spec/spec.md`) and composes with Roles &
Permissions (`specs/003-roles-permissions/spec.md`), Events & History (`specs/007-events-history/spec.md`),
Notifications (`specs/010-notifications/spec.md`), Gamification & Economy
(`specs/013-gamification-economy/spec.md`), Campaigns (`specs/014-campaigns/spec.md`), Support
(`specs/016-support/spec.md`), and AI (`specs/018-ai-capability/spec.md`), under the project Constitution
(`.specify/memory/constitution.md`, v1.0.0). It draws on `product/PRODUCT_BLUEPRINT.md`,
`product/BUSINESS_RULES.md`, and `architecture/EVENT_MODEL.md`.

### Scope & Non-Goal (normative)

- The engine is **transversal** — any domain can produce triggers and consume actions through it.
- It is **NOT a full general-purpose workflow builder** (not an n8n clone): it provides a bounded
  WHEN→IF→THEN model, not arbitrary branching/looping dataflow programming.
- Automations **MUST NOT bypass permissions**; every action runs within the **authoring user's**
  effective permissions (or a clearly-scoped system identity for portal/admin automations).
- Actions are **audited**; the engine enforces **loop prevention, repeat prevention, timeouts, and
  automatic suspension on repeated errors**.
- **AI MAY be used within an automation**, but **critical rules MUST remain deterministic** (AI is never
  the decider for a critical/sensitive outcome without a deterministic gate + confirmation where
  required).

Scope boundary: this spec **owns** the automation definition, trigger/condition/action model,
execution, execution history, and safety constraints. It **consumes** the event backbone (triggers),
the authorization engine (bounding), and each action's owning domain (Notifications, Gamification,
Support, Connectors, Content, AI, etc.) — it never re-implements those. It chooses no technology and
contains no implementation detail.

**Terminology**: Automation = a WHEN/IF/THEN rule; Trigger (WHEN) = the event/condition that starts
evaluation; Condition (IF) = a filter that must hold; Action (THEN) = an authorized effect; Domain Event
= a recorded fact; `occurred_at` = real occurrence time.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Define and run a WHEN → IF → THEN automation (Priority: P1)

An authorized user defines an automation: WHEN a trigger fires, IF conditions hold, THEN perform one or
more authorized actions. When the trigger occurs and conditions hold, the actions run within the
author's permissions and the run is recorded.

**Why this priority**: The WHEN/IF/THEN execution is the core of the engine; everything else is safety
and breadth around it.

**Independent Test**: Define an automation triggered by a domain event with a condition and a
non-sensitive authorized action; fire the trigger; confirm the condition is evaluated, the action runs
within permissions, and an execution-history entry is recorded.

**Acceptance Scenarios**:

1. **Given** an automation WHEN event X IF condition Y THEN action Z, **When** X fires and Y holds,
   **Then** Z runs within the author's permissions and an execution record is created.
2. **Given** the same automation, **When** Y does not hold, **Then** no action runs and the (no-op)
   evaluation may be recorded.
3. **Given** an automation, **When** it runs, **Then** it emits an execution event with `occurred_at`
   distinct from `received_at`.

### User Story 2 - Permission-bounded actions (no bypass) (Priority: P1)

Every automation action runs within the authoring user's effective permissions (or a scoped system
identity for portal automations); an action the author could not perform manually is refused.

**Why this priority**: "No automation can bypass permissions" is a locked constraint and the highest
security risk for an action engine.

**Independent Test**: Define an automation whose action exceeds the author's permissions; fire it;
confirm the action is refused server-side and recorded as refused — not silently escalated.

**Acceptance Scenarios**:

1. **Given** an automation whose action exceeds the author's permissions, **When** it would run, **Then**
   the action is refused server-side and recorded.
2. **Given** a portal/admin automation using a scoped system identity, **When** it runs, **Then** it is
   bounded by that identity's explicitly granted permissions (never unbounded).
3. **Given** the author's permissions change, **When** the automation next runs, **Then** it is
   re-evaluated against current permissions.

### User Story 3 - Sensitive actions, approval, and deterministic critical rules (Priority: P1)

Sensitive actions within an automation require approval/confirmation where appropriate; critical rules
remain deterministic even if the automation uses AI for non-critical assistance.

**Why this priority**: Encodes the locked rules that sensitive actions are confirmed and that critical
outcomes stay deterministic (AI may assist, not decide critical outcomes unchecked).

**Independent Test**: Define an automation with a sensitive action and an AI-assisted step; fire it;
confirm the sensitive action routes through the required approval, and that the critical decision is
made by a deterministic rule (AI output alone never triggers the critical/sensitive effect without the
deterministic gate + approval).

**Acceptance Scenarios**:

1. **Given** an automation with a sensitive action, **When** it would execute, **Then** it requires the
   configured approval/confirmation before proceeding.
2. **Given** an automation that invokes AI, **When** the outcome is critical/sensitive, **Then** a
   deterministic rule governs the decision and AI output alone does not cause the sensitive effect.
3. **Given** AI is used for non-critical assistance (e.g., drafting a message), **When** it runs, **Then**
   it is bounded by the automation's permissions and never escalates them.

### User Story 4 - Broad triggers across the portal (Priority: P2)

Automations can be triggered by a wide range of domain events — service state changes, new media,
request changes, achievements, level reached, campaign start/end, maintenance, ticket created/changed,
project created/funded, news published, marketplace events, plugin events, and system events.

**Why this priority**: Trigger breadth is explicit and is what makes the engine transversal.

**Independent Test**: For a representative subset of trigger types, define an automation and fire the
corresponding event; confirm each trigger type can start an automation.

**Acceptance Scenarios**:

1. **Given** each listed trigger type, **When** the corresponding domain event occurs, **Then** a
   subscribed automation can be triggered.
2. **Given** a trigger from a plugin/system source, **When** it fires, **Then** it is handled by the same
   WHEN/IF/THEN model (no special parallel path).
3. **Given** a time-based trigger (e.g., schedule), **When** its moment is reached, **Then** it fires
   like any trigger (bounded scope — not arbitrary cron programming). (See OQ-90.)

### User Story 5 - Rich structured conditions (Priority: P2)

Conditions can filter on user, role, level, service, media, genre, event/campaign, time, permissions,
and other structured conditions, combined deterministically.

**Why this priority**: Conditions make automations precise and safe; deterministic combination avoids
ambiguous firing.

**Independent Test**: Define an automation with combined conditions (e.g., role + level + genre + time
window); fire it in matching and non-matching contexts; confirm it runs only when all conditions
deterministically hold.

**Acceptance Scenarios**:

1. **Given** conditions on user/role/level/service/media/genre/event/time/permissions, **When**
   evaluated, **Then** the automation runs only if the combined conditions deterministically hold.
2. **Given** a permission-based condition, **When** evaluated, **Then** it reflects the subject's current
   permissions (and never grants access).
3. **Given** combined conditions, **When** evaluated, **Then** the combination is deterministic and
   order-independent in outcome.

### User Story 6 - Broad authorized actions (Priority: P2)

Automations can perform a wide range of actions — notification, email, create ticket/incident, award
XP/Coins/Contribution, unlock reward, publish content, synchronize, update status, connector action,
request approval, invoke AI, and trigger another automation — each executed through its owning domain and
within permissions.

**Why this priority**: Action breadth is explicit; routing each through its owning domain prevents
parallel mechanisms (principle XX).

**Independent Test**: For a representative subset of action types, define an automation that performs it;
fire it; confirm each action executes through its owning domain, within permissions, and is recorded.

**Acceptance Scenarios**:

1. **Given** each listed action type, **When** an automation performs it, **Then** it executes through
   the owning domain (Notifications/Gamification/Support/Connectors/Content/AI/etc.) within permissions.
2. **Given** an award action (XP/Coins/Contribution/reward), **When** performed, **Then** it goes through
   Gamification's rules/ledger/anti-abuse (not a parallel grant).
3. **Given** a "trigger another automation" action, **When** performed, **Then** loop prevention applies
   (see US7) and the chain is bounded.

### User Story 7 - Loop prevention, repeat prevention, timeout (Priority: P1)

The engine prevents runaway loops (including automation-triggers-automation chains), prevents
unintended repeated firing for the same occurrence, and bounds each execution with a timeout.

**Why this priority**: These are explicit locked safety constraints; without them an action engine can
cascade or storm.

**Independent Test**: Create an automation that could trigger itself (directly or via a chain); fire it;
confirm loop prevention stops runaway execution; re-deliver the same triggering occurrence and confirm no
duplicate firing; make an action hang and confirm the timeout bounds it.

**Acceptance Scenarios**:

1. **Given** an automation that could re-trigger itself (directly or through a chain), **When** it runs,
   **Then** loop prevention stops runaway execution and records the prevention.
2. **Given** duplicate/late delivery of the same triggering occurrence, **When** evaluated, **Then** the
   automation does not fire twice for the same occurrence (repeat prevention; idempotent on `occurred_at`).
3. **Given** an action that hangs, **When** it exceeds the timeout, **Then** execution is bounded/aborted
   and recorded, without leaving a partial sensitive action unconfirmed.

### User Story 8 - Auto-suspension on repeated errors + execution history (Priority: P1)

An automation that errors repeatedly is automatically suspended to protect the portal; all runs
(success, no-op, refused, prevented, timed-out, suspended) are recorded in execution history and
sensitive actions are audited.

**Why this priority**: Auto-suspension and full execution history are explicit safety/observability
constraints essential to trust.

**Independent Test**: Make an automation fail repeatedly; confirm it auto-suspends after the configured
threshold, is reported to the owner/admin, and requires explicit re-enable; confirm every run is in
execution history and sensitive actions are audited.

**Acceptance Scenarios**:

1. **Given** an automation failing repeatedly, **When** it crosses the error threshold, **Then** it is
   automatically suspended and the owner/admin is informed per preferences.
2. **Given** a suspended automation, **When** anything triggers it, **Then** it does not run until
   explicitly re-enabled (a permissioned, audited action).
3. **Given** any execution (success/no-op/refused/prevented/timeout/suspend), **When** it occurs, **Then**
   it is recorded in execution history; sensitive actions are audited (actor/author, action, timestamp,
   context, result).

### Edge Cases

- **Automation triggers itself (direct/indirect)**: Loop prevention detects and stops the cycle; the
  chain depth is bounded; the prevention is recorded.
- **Duplicate/late trigger event**: Repeat prevention ensures one firing per logical occurrence
  (idempotent on `occurred_at`); a redelivered event does not re-fire.
- **Action exceeds author permissions**: Refused server-side and recorded; never escalated.
- **Author permissions reduced after creation**: On next run, re-evaluated against current permissions;
  newly unauthorized actions are refused.
- **Sensitive action without approval**: Not executed until the required approval/confirmation is given.
- **AI step fails or is unavailable**: The automation degrades per its definition; critical outcomes
  stay deterministic; AI failure never forces or skips a sensitive effect.
- **AI drives a critical decision**: Not allowed — a deterministic rule governs critical/sensitive
  outcomes; AI may only assist non-critically.
- **Action hangs**: Timeout bounds the execution; partial sensitive effects are not left unconfirmed.
- **Repeated failures**: Auto-suspension after the configured threshold; requires explicit, audited
  re-enable.
- **Connector action to an unavailable service**: Fails gracefully, recorded; does not break unrelated
  automations or portal functions.
- **Award action farmed via automation**: Gamification anti-abuse (cooldown/caps/diminishing/anomaly)
  still applies; automations cannot farm rewards.
- **Mass trigger storm**: The engine throttles/batches within policy so one noisy trigger does not
  overwhelm the portal; critical safety actions are not dropped silently.
- **Plugin-provided trigger/action fails**: Isolated; a failing plugin automation does not break
  unrelated functions.
- **Account deletion of an automation's author**: The automation is suspended/resolved per policy;
  execution history anonymized but integrity-preserving.

## Requirements *(mandatory)*

### Functional Requirements

#### Model & Execution (WHEN → IF → THEN)
- **FR-001**: The engine MUST implement a bounded WHEN→IF→THEN model: a trigger starts evaluation, all
  conditions must hold, then the configured actions run; it MUST NOT be a general-purpose/arbitrary
  dataflow workflow builder.
- **FR-002**: When a trigger fires and conditions hold, the configured actions MUST run within the
  authoring user's effective permissions (or a clearly-scoped system identity for portal/admin
  automations).
- **FR-003**: Every execution (success, no-op, refused, prevented, timeout, suspended) MUST be recorded
  in execution history and MUST emit an execution domain event with `occurred_at` distinct from
  `received_at`.

#### Permission Boundaries (no bypass)
- **FR-004**: An automation MUST NOT bypass permissions; an action the author (or scoped system identity)
  could not perform MUST be refused server-side and recorded.
- **FR-005**: Automations MUST be re-evaluated against current permissions at run time; a reduction in
  the author's permissions MUST take effect on the next run.
- **FR-006**: A portal/admin automation using a system identity MUST be bounded by that identity's
  explicitly granted permissions and MUST NOT be unbounded.

#### Sensitive Actions, Approval & Deterministic Critical Rules
- **FR-007**: Sensitive actions within an automation MUST require the configured approval/confirmation
  before execution and MUST be audited.
- **FR-008**: Critical/sensitive outcomes MUST be governed by deterministic rules; when an automation
  uses AI, AI output alone MUST NOT cause a critical/sensitive effect without a deterministic gate (and
  approval where required).
- **FR-009**: AI used for non-critical assistance within an automation MUST be bounded by the
  automation's permissions and MUST NOT escalate them.

#### Triggers (WHEN)
- **FR-010**: The engine MUST support triggers for at least: service state changed, new media, request
  changed, achievement, level reached, campaign start/end, maintenance, ticket created/changed, project
  created/funded, news published, marketplace event, plugin event, and system event.
- **FR-011**: Triggers MUST be sourced from the domain-event backbone and handled by the same WHEN/IF/THEN
  model regardless of origin (including plugin/system sources).
- **FR-012**: The engine MUST support time/schedule-based triggers within a bounded scope (not arbitrary
  cron programming).

#### Conditions (IF)
- **FR-013**: The engine MUST support conditions on at least: user, role, level, service, media, genre,
  event/campaign, time, permissions, and other structured conditions.
- **FR-014**: Combined conditions MUST evaluate deterministically (order-independent outcome); a
  permission-based condition MUST reflect current permissions and MUST NOT grant access.

#### Actions (THEN)
- **FR-015**: The engine MUST support actions including: notification, email, create ticket, create
  incident, award XP, award Coins, award Contribution, unlock reward, publish content, synchronize,
  update status, connector action, request approval, invoke AI, and trigger another automation.
- **FR-016**: Every action MUST execute through its owning domain (Notifications/Gamification/Support/
  Connectors/Content/AI/etc.) under that domain's rules — no parallel mechanism (principle XX).
- **FR-017**: Award actions MUST go through Gamification's rules/ledger/anti-abuse; automations MUST NOT
  be a path to farm rewards or bypass anti-abuse.
- **FR-018**: A "trigger another automation" action MUST be subject to loop/chain-depth prevention.

#### Safety: Loop / Repeat / Timeout / Auto-Suspension
- **FR-019**: The engine MUST prevent runaway loops, including automation-triggers-automation chains, with
  bounded chain depth, recording any prevention.
- **FR-020**: The engine MUST prevent unintended repeated firing for the same logical occurrence
  (idempotent on `occurred_at`).
- **FR-021**: Each execution MUST be bounded by a timeout; a hung action MUST be aborted/bounded and
  recorded without leaving a partial sensitive action unconfirmed.
- **FR-022**: An automation that errors repeatedly MUST be automatically suspended after a configured
  threshold, the owner/admin informed, and it MUST require an explicit, permissioned, audited re-enable.
- **FR-023**: The engine MUST throttle/batch under trigger storms within policy, without silently
  dropping critical safety actions.

#### Audit, History, Resilience, Privacy
- **FR-024**: Sensitive automation actions MUST be audited (author, action, timestamp, context, result);
  defining/enabling/disabling/suspending/re-enabling an automation MUST be permissioned and audited.
- **FR-025**: Execution history MUST retain provenance (trigger, conditions evaluated, actions attempted/
  performed, outcome) and MUST NOT be automatically public; it MUST follow the privacy/deletion
  lifecycle.
- **FR-026**: A failing automation (including plugin-provided) MUST be isolated so it does not break
  unrelated automations or portal functions.
- **FR-027**: Automations MUST NOT expose secrets or another user's private data by permission alone; AI
  and connector actions within automations MUST respect privacy.

### Automation & Execution State Models

**Automation states**: Draft → Enabled → Disabled; Enabled → Suspended (auto, on repeated errors) →
Enabled (manual re-enable); any → Archived.

**Execution outcomes**: Evaluated-NoOp, Succeeded, Partially-Succeeded, Refused (permission), Prevented
(loop/repeat), Timed-Out, Error, Awaiting-Approval.

**Invariants**:
- An automation runs only while Enabled.
- Suspension requires explicit, audited re-enable.
- Every trigger evaluation produces an execution record (even no-op/refused/prevented).
- Actions always run within permissions; sensitive ones await approval; critical outcomes deterministic.

### Worked Example (illustrative)

- **WHEN** `service.status_changed` to Unavailable **IF** the service is user-facing AND no open incident
  exists **THEN** create an incident (deterministic) AND notify subscribers (via Notifications) —
  incident creation is the deterministic critical action; an optional AI step may draft the incident
  summary (non-critical assistance), and a sensitive escalation action would require approval.
- Loop prevention ensures the resulting `incident.created` event does not re-trigger the same automation;
  repeat prevention ensures a flapping service does not spam incidents.

### Automation-Related Domain Events

- `automation.created`, `automation.updated`, `automation.enabled`, `automation.disabled`,
  `automation.suspended`, `automation.reenabled`
- `automation.execution_started`, `automation.execution_completed` (with outcome),
  `automation.loop_prevented`, `automation.repeat_prevented`, `automation.timed_out`
- Action effects reuse the owning domains' events (e.g., `ticket.created`, `reward.granted`).

### Key Entities

- **Automation**: A WHEN/IF/THEN rule with author (or system identity), trigger, conditions, actions,
  state, and safety settings (timeout, chain-depth limit, error threshold), versioned.
- **Trigger**: The subscribed domain event/time condition that starts evaluation.
- **Condition**: A structured filter (user/role/level/service/media/genre/event/time/permissions/…).
- **Action**: An authorized effect executed through its owning domain.
- **Automation Execution**: A recorded run with trigger reference, conditions evaluated, actions
  attempted/performed, and outcome.
- **Approval Request (referenced)**: A gate for a sensitive action within an automation.
- **Permission/System Identity (referenced)**: The bounding authority for the automation's actions.
- **Owning domains (referenced)**: Notifications, Gamification, Support, Connectors, Content, AI, etc.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An automation performs an action beyond its author's/identity's permissions in 0% of cases
  (refused and recorded).
- **SC-002**: A sensitive automation action executes without the required approval/confirmation in 0% of
  cases.
- **SC-003**: A critical/sensitive outcome is decided by AI output alone (without a deterministic gate)
  in 0% of cases.
- **SC-004**: A runaway loop (direct or via chain) escapes loop prevention in 0% of cases; chain depth is
  bounded in 100% of cases.
- **SC-005**: The same logical triggering occurrence fires an automation more than once in 0% of cases
  (repeat prevention; idempotent).
- **SC-006**: A hung action exceeds its timeout without being bounded/aborted in 0% of cases; no partial
  sensitive action is left unconfirmed in 100% of timeout cases.
- **SC-007**: An automation failing past the error threshold remains active in 0% of cases (auto-suspends
  in 100%); re-enable without explicit permissioned action occurs in 0% of cases.
- **SC-008**: Every trigger evaluation produces an execution-history record in 100% of cases; sensitive
  actions are audited in 100% of cases.
- **SC-009**: An award action via automation bypasses Gamification anti-abuse in 0% of cases.
- **SC-010**: A failing/plugin automation breaks unrelated automations or portal functions in 0% of
  cases; it is not a general-purpose dataflow builder (bounded WHEN/IF/THEN) in 100% of cases.

## Assumptions

- Triggers come from the event backbone; each action's owning domain enforces its own rules; this engine
  orchestrates within permissions and never re-implements domain logic.
- The authorization engine, Gamification (awards/anti-abuse), Notifications, Support, Connectors, Content,
  and AI are owned by their specs; automations compose with them.
- The exact error threshold, timeout values, chain-depth limit, and throttling policy are configurable
  administrative data. (Flagged as OQ-91.)
- "Critical/sensitive" actions are at least the Constitution/Permissions set plus any domain-marked ones;
  the deterministic-gate requirement applies to all of them. (Flagged as OQ-92.)
- Who may create automations (which roles) and over which scopes is administrative policy. (Flagged as
  OQ-93.)

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation.

- **OQ-90 (Time-trigger scope)**: Confirm how far time/schedule triggers go (fixed relative points vs
  recurring schedules) without becoming a general cron/workflow tool.
- **OQ-91 (Safety thresholds)**: Confirm default timeout, error threshold for auto-suspension,
  chain-depth limit, and storm throttling policy (global vs per-automation).
- **OQ-92 (Critical-action catalog)**: Confirm the exact set of actions treated as critical/sensitive
  (requiring deterministic gate + approval), aligned with Permissions (OQ-13/14) and AI (OQ-86).
- **OQ-93 (Authoring scope)**: Confirm which roles may author automations, whether non-admin users may
  create personal automations, and the bounds of a portal/admin system identity.
- **OQ-94 (AI-in-automation boundary)**: Confirm precisely where AI may participate (assist/draft/suggest)
  vs where it is forbidden (deciding critical outcomes), aligned with the AI spec.

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference) and the project
  Constitution (v1.0.0).
- Composes with: `specs/003-roles-permissions/spec.md` (`automation.manage`; action bounding; audit),
  `specs/007-events-history/spec.md` (triggers; idempotency on `occurred_at`; execution events),
  `specs/010-notifications/spec.md` (notification/email actions), `specs/013-gamification-economy/spec.md`
  (award actions via rules/ledger/anti-abuse), `specs/014-campaigns/spec.md` (campaign start/end
  triggers), `specs/016-support/spec.md` (create ticket/incident actions), and
  `specs/018-ai-capability/spec.md` (invoke-AI action; AI never exceeds permissions, non-critical only).
- Depends on / references: `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`,
  `architecture/EVENT_MODEL.md`, `architecture/DATA_MODEL.md`.
- Related specs (not owned here): Connectors (connector actions/synchronize), Content (publish),
  Services & Health (status/maintenance triggers), Marketplace (marketplace events), the Extension
  Registry (plugin triggers/actions), and the Privacy spec (021) (visibility).
