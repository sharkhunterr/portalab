# Feature Specification: Support

**Feature Branch**: `016-support`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Detailed functional specification of the Support system (tickets, incidents, feedback, AI diagnosis)."

## Role of This Document

This is a **detailed feature specification** for Support — tickets (types, custom fields, tags, states,
workflows, transitions, assignment, attachments), incidents, feedback (forms, bug reports, feature
requests), support roles/permissions, and AI-assisted diagnosis before ticket creation. It conforms to
and refines the superior reference specification (`specs/001-portal-global-spec/spec.md`) and composes
with Roles & Permissions (`specs/003-roles-permissions/spec.md`), Services & Health
(`specs/006-services-health/spec.md`), Events & History (`specs/007-events-history/spec.md`), Search &
AI (`specs/008-search-command-palette/spec.md`), Content/Wiki (`specs/011-content-news-wiki-calendar/spec.md`),
Notifications (`specs/010-notifications/spec.md`), Community (`specs/012-community/spec.md`), and
Gamification (`specs/013-gamification-economy/spec.md`), under the project Constitution
(`.specify/memory/constitution.md`, v1.0.0). It draws on `product/PRODUCT_BLUEPRINT.md`,
`product/BUSINESS_RULES.md`, and `ux/USER_JOURNEYS.md`.

Scope boundary: this spec **owns** tickets, the incident concept and surfacing, feedback (forms, bug
reports, feature requests) and its conversion paths, support roles/workflows, and the AI diagnosis flow
that prefills a ticket for user confirmation. It **consumes** the AI engine, the Wiki (knowledge),
Services & Health (service state to check), the authorization/privacy/notification/event engines, and
Community/Gamification (as feedback conversion targets). It does **not** own the AI engine, the Wiki, the
service-health model, or the Community/Gamification engines. It chooses no technology and contains no
implementation detail.

### Strict Conceptual Distinctions (normative)

These are **distinct** and MUST NOT be conflated (consistent with Services & Health):

- **Incident** = a broad/systemic problem potentially affecting multiple users, with its own lifecycle
  (created/updated/resolved). Surfaced to reduce duplicate tickets.
- **Ticket** = an individual user's issue, with type/workflow/assignment. A Ticket MAY reference an
  Incident but is never the same thing.
- **Feedback** = a structured collection of an opinion or piece of information (via forms, bug reports,
  feature requests). Feedback is not a Ticket or an Incident by itself.

**Feedback conversion**: a Feedback item MAY be converted into a **contribution**, a **ticket**, a
**feature proposal**, or a **community project** — each conversion is explicit, preserves provenance
(the original feedback), and hands off to the owning domain.

**Terminology**: Domain Event = a recorded fact; `occurred_at` = real occurrence time. Support roles
(e.g., Support, Moderator) come from the Permission Model.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create and track a ticket through its workflow (Priority: P1)

A user creates a ticket of a given type, provides the required fields/attachments, and tracks it through
its workflow states to resolution; support staff triage, assign, transition, and respond.

**Why this priority**: Tickets are the core of Support; without reliable creation, workflow, and
tracking there is no support system.

**Independent Test**: Create a ticket of a type with custom fields; attach a file; move it through its
workflow states (with valid transitions only); assign it; resolve it; confirm the user can track status
throughout.

**Acceptance Scenarios**:

1. **Given** a ticket type with required custom fields, **When** a user creates a ticket, **Then** it is
   created only if required fields are provided, with any attachments, and a `ticket.created` event is
   recorded.
2. **Given** a ticket, **When** a support agent transitions it, **Then** only valid transitions for its
   workflow are allowed and each transition is recorded.
3. **Given** a ticket, **When** assigned to an agent, **Then** the assignment is recorded and the agent/
   user are notified per preferences.
4. **Given** a ticket, **When** resolved, **Then** its state becomes resolved/closed and a
   `ticket.resolved` event is recorded; the requester can see the resolution.

### User Story 2 - Ticket types, custom fields, tags (Priority: P2)

Support defines ticket types (e.g., bug, request, question, service issue), each with its own custom
fields and applicable workflow; tickets can be tagged for triage and filtering.

**Why this priority**: Types/fields/tags structure the queue and make triage and reporting possible.

**Independent Test**: Define two ticket types with different custom fields and workflows; create a ticket
of each; tag them; filter the queue by type/tag; confirm each type's fields/workflow apply.

**Acceptance Scenarios**:

1. **Given** multiple ticket types, **When** a user selects one, **Then** its specific custom fields and
   workflow apply.
2. **Given** tags, **When** applied to tickets, **Then** the queue can be filtered/grouped by tag and
   type.
3. **Given** a custom field marked required, **When** a ticket is created without it, **Then** creation is
   refused with the missing field named.

### User Story 3 - Incidents distinct from tickets, surfaced to reduce duplicates (Priority: P1)

When a systemic incident exists, it is surfaced to users starting a related ticket so they see the known
issue and avoid filing duplicates; incidents have their own lifecycle independent of any ticket.

**Why this priority**: The incident/ticket distinction and duplicate reduction are explicit, locked
Support rules.

**Independent Test**: Open an incident; start a related ticket as a user; confirm the known incident is
surfaced; confirm the incident lifecycle is independent (it can resolve while tickets remain, or persist
after a ticket closes).

**Acceptance Scenarios**:

1. **Given** an open incident related to a user's problem, **When** the user starts a ticket, **Then**
   the known incident is surfaced to reduce duplicate tickets.
2. **Given** an incident and tickets, **When** compared, **Then** they are distinct records with
   independent lifecycles (a ticket MAY link an incident; it is never the same).
3. **Given** an incident resolves, **When** it does, **Then** linked tickets are not auto-forced to
   resolve (they follow their own workflow), though agents MAY resolve them.

### User Story 4 - Feedback: forms, bug reports, feature requests (Priority: P2)

A user submits structured feedback via a form (general feedback, bug report, or feature request);
feedback is captured distinctly from tickets/incidents and can be reviewed.

**Why this priority**: Feedback is a distinct structured-collection concept and the entry point for the
conversion paths.

**Independent Test**: Submit each feedback kind via its form; confirm it is captured as feedback (not a
ticket), with its structured fields, reviewable by permitted staff.

**Acceptance Scenarios**:

1. **Given** a feedback form, **When** a user submits general feedback, a bug report, or a feature
   request, **Then** it is captured as structured Feedback with its fields and a `feedback.created`
   event.
2. **Given** feedback, **When** reviewed, **Then** it is distinct from tickets and incidents and retains
   its structure.
3. **Given** a bug report feedback, **When** it clearly describes an individual issue, **Then** staff MAY
   convert it to a ticket (see US5) rather than treating feedback as a ticket automatically.

### User Story 5 - Feedback conversion: contribution / ticket / feature proposal / community project (Priority: P2)

Permitted staff convert a feedback item into a contribution, a ticket, a feature proposal, or a community
project; the conversion preserves provenance and hands off to the owning domain.

**Why this priority**: The explicit conversion paths connect Support to Gamification/Community/Marketplace
without duplicating those systems.

**Independent Test**: Convert one feedback item into each target (contribution, ticket, feature proposal,
community project); confirm the target is created in its owning domain, provenance to the original
feedback is preserved, and no duplicate parallel mechanism is created.

**Acceptance Scenarios**:

1. **Given** a feedback item, **When** converted to a ticket, **Then** a ticket is created (Support) with
   provenance to the feedback.
2. **Given** a feedback item, **When** converted to a feature proposal or community project, **Then** it
   is created in Community/Marketplace (owning domain) with provenance; votes/funding follow those specs.
3. **Given** a feedback item, **When** recognized as a contribution, **Then** Contribution is granted via
   Gamification's rules (not a parallel reward), attributed to the author, within anti-abuse limits.
4. **Given** any conversion, **When** performed, **Then** the original feedback is preserved (provenance
   not lost) and the action is recorded/audited.

### User Story 6 - AI-assisted diagnosis before ticket creation (Priority: P1)

Before a user files a ticket, the AI can run a diagnosis flow — identify the user, check the service,
consult the Wiki, analyze state, propose a solution, and (if needed) create and prefill a ticket — always
leaving the user to confirm or modify before submission, and always within the user's permissions.

**Why this priority**: The AI diagnosis flow is explicitly specified step-by-step and is a key
reliability/UX feature; it must never bypass permissions or submit without user confirmation.

**Independent Test**: Trigger AI diagnosis on a service problem; confirm it performs the steps (identify
user, check service, consult Wiki, analyze state, propose solution), and that if a ticket is warranted it
is prefilled and left for the user to confirm/modify — never auto-submitted, never exceeding the user's
permissions.

**Acceptance Scenarios**:

1. **Given** a user with a problem, **When** AI diagnosis runs, **Then** it (1) identifies the user, (2)
   checks the relevant service state, (3) consults permitted Wiki content, (4) analyzes the state, and
   (5) proposes a solution — all within the user's permissions.
2. **Given** the proposed solution resolves the issue, **When** accepted, **Then** no ticket need be
   created (duplicate avoidance).
3. **Given** a ticket is warranted, **When** the AI creates it, **Then** it (6) creates the ticket, (7)
   prefills the technical context, and (8) leaves the user to confirm or modify before submission — never
   auto-submitting.
4. **Given** AI diagnosis, **When** it runs, **Then** it never accesses data the user may not see and
   never exceeds the user's permissions; an AI failure MUST NOT block manual ticket creation.

### User Story 7 - Support roles, permissions, assignment, attachments (Priority: P1)

Support operations are permission-gated: support roles can triage/assign/transition/respond; users can
create/track their own tickets; attachments are handled safely; sensitive actions are audited.

**Why this priority**: Permissioning and safe attachment handling protect privacy and integrity across
the support queue.

**Independent Test**: As a support role, triage/assign/transition a ticket; as a requester, create/track
but not administer; upload an attachment and confirm safe handling; confirm sensitive actions are audited
and private data is protected.

**Acceptance Scenarios**:

1. **Given** a support role, **When** acting on tickets, **Then** permitted triage/assignment/transition/
   response actions succeed; a requester MUST only create/track/respond to their own tickets.
2. **Given** an attachment, **When** uploaded, **Then** it is handled safely (validated, no unsafe
   execution, no secret exposure) and visible only to permitted parties.
3. **Given** ticket content, **When** viewed, **Then** it respects privacy — a requester's private data is
   not exposed beyond permitted support staff and the requester.
4. **Given** sensitive support actions (reassignment across users, closing another's ticket, viewing
   restricted content), **When** performed, **Then** they are audited.

### Edge Cases

- **Duplicate ticket for a known incident**: The user is shown the known incident before filing; if they
  still file, agents can link/merge per policy without losing the requester's record.
- **Invalid workflow transition**: A transition not allowed by the ticket type's workflow is refused;
  only defined transitions are possible.
- **AI auto-submit attempt**: The AI never submits a ticket on its own; a prefilled ticket always awaits
  user confirmation/modification.
- **AI exceeding permissions**: AI diagnosis never reads a service/Wiki/user datum the requester may not
  see; it is bounded to the user's permissions exactly as the user would be.
- **AI unavailable**: Manual ticket creation remains fully available; AI failure does not block Support.
- **Feedback treated as ticket automatically**: Feedback is not auto-converted; conversion is an explicit
  permitted action preserving provenance.
- **Conversion into owning domain**: Converting to a community project/feature proposal creates it in
  Community/Marketplace (not a Support-local clone); contribution grants go through Gamification.
- **Attachment safety**: Attachments are validated/sanitized; executable/unsafe content is not run; size/
  type limits apply; secrets are never exposed.
- **Requester privacy**: A requester's private data in a ticket is visible only to the requester and
  permitted support staff; never public by permission alone.
- **Incident resolves with open tickets**: Linked tickets are not force-closed; they follow their own
  workflow.
- **Permission change mid-ticket**: On next evaluation, a user who lost access no longer sees restricted
  ticket content; agents' scope re-evaluates server-side.
- **Account deletion with open tickets/feedback**: Resolve/anonymize per the deletion lifecycle; identity
  removed/anonymized while integrity-necessary records (e.g., incident linkage counts) preserved.

## Requirements *(mandatory)*

### Functional Requirements

#### Tickets — Creation, Types, Fields, Tags
- **FR-001**: The system MUST support creating tickets of defined types, each type carrying its own custom
  fields and applicable workflow.
- **FR-002**: Required custom fields MUST be enforced at creation; creation MUST be refused (naming the
  missing field) if a required field is absent.
- **FR-003**: Tickets MUST support tags for triage, filtering, and grouping.
- **FR-004**: Tickets MUST support attachments, validated and sanitized, with no unsafe execution and no
  secret exposure, visible only to permitted parties.

#### Tickets — States, Workflows, Transitions, Assignment
- **FR-005**: Each ticket type MUST define a workflow of states and allowed transitions; only defined
  transitions MUST be permitted.
- **FR-006**: Tickets MUST support assignment to support agents; assignment MUST be recorded and relevant
  parties notified per preferences.
- **FR-007**: Ticket state changes and transitions MUST be recorded and MUST emit `ticket.created`,
  `ticket.updated`, `ticket.resolved` events with `occurred_at` distinct from `received_at`.

#### Incidents (distinct from tickets)
- **FR-008**: The system MUST model Incidents as broad/systemic problems with their own lifecycle
  (created/updated/resolved), distinct from tickets.
- **FR-009**: Known incidents MUST be surfaced to users starting a related ticket to reduce duplicates.
- **FR-010**: A ticket MAY reference an incident, but the two MUST remain distinct with independent
  lifecycles; resolving an incident MUST NOT auto-force linked tickets to resolve.

#### Feedback (forms, bug reports, feature requests)
- **FR-011**: The system MUST support structured Feedback via forms, including at least general feedback,
  bug reports, and feature requests, captured distinctly from tickets and incidents.
- **FR-012**: Feedback MUST retain its structured fields and MUST be reviewable by permitted staff; a
  `feedback.created` event MUST be recorded.
- **FR-013**: Feedback MUST NOT be automatically treated as a ticket; any conversion MUST be explicit.

#### Feedback Conversion
- **FR-014**: Permitted staff MUST be able to convert a feedback item into: a contribution, a ticket, a
  feature proposal, or a community project.
- **FR-015**: Each conversion MUST create the target in its owning domain (ticket in Support; feature
  proposal/community project in Community/Marketplace; contribution via Gamification) — never a parallel
  Support-local clone.
- **FR-016**: Each conversion MUST preserve provenance (link to the original feedback) and MUST be
  recorded/audited; the original feedback MUST NOT be destroyed by conversion.

#### AI-Assisted Diagnosis
- **FR-017**: The system MUST support an AI diagnosis flow before ticket creation that: (1) identifies the
  user, (2) checks the relevant service state, (3) consults permitted Wiki content, (4) analyzes the
  state, (5) proposes a solution, (6) creates a ticket if needed, (7) prefills technical context, and (8)
  leaves the user to confirm or modify before submission.
- **FR-018**: The AI MUST operate strictly within the requesting user's permissions and MUST NOT access
  any data the user may not see.
- **FR-019**: The AI MUST NOT auto-submit a ticket; a prefilled ticket MUST always await the user's
  explicit confirmation/modification.
- **FR-020**: An AI failure or unavailability MUST NOT block manual ticket creation or other Support
  functions.
- **FR-021**: AI-proposed solutions MUST be distinguishable as AI interpretation versus real data/state.

#### Support Roles & Permissions
- **FR-022**: Support operations MUST be permission-gated (deny-by-default, server-side): support roles may
  triage/assign/transition/respond; requesters may create/track/respond to their own tickets only.
- **FR-023**: Ticket/feedback content MUST respect privacy: a requester's private data MUST be visible only
  to the requester and permitted support staff, never public by permission alone.
- **FR-024**: Sensitive support actions (cross-user reassignment, closing another's ticket, viewing
  restricted content, conversions) MUST be audited with actor, action, timestamp, context, result.

#### Cross-Cutting (notifications, events, history, degraded, deletion)
- **FR-025**: Support notifications (new assignment, status change, resolution, incident surfaced) MUST be
  produced only via the notification engine, respecting preferences/permissions.
- **FR-026**: Support history/provenance MUST be retained; historized support data MUST NOT be public by
  default and MUST follow the privacy/deletion lifecycle (identity anonymized/removed at final deletion;
  integrity records preserved non-identifying).
- **FR-027**: Support surfaces MUST degrade gracefully: if a source (service health, Wiki, AI) is slow/
  unavailable, Support remains usable and the affected part shows its functional state.
- **FR-028**: Support MUST consume Services & Health, Wiki, AI, Community/Gamification via their contracts
  (no parallel mechanisms) consistent with the capability/decoupling principles.

### Ticket State Model (illustrative baseline)

**States**: New → Triaged → In Progress → Waiting (on user/third party) → Resolved → Closed; plus
Reopened (from Resolved/Closed) per workflow.

**Invariants**:
- Each ticket type defines its own workflow; only defined transitions are allowed.
- A ticket's lifecycle is independent of any linked Incident's lifecycle.
- Resolution/closure is recorded; reopening is a defined transition, not a rewrite of history.
- The exact per-type workflows are configurable (see OQ-75).

### AI Diagnosis Flow (normative sequence)

1. Identify the user (within their session/permissions).
2. Check the relevant service state (via Services & Health, permitted data only).
3. Consult the Wiki (permitted pages only).
4. Analyze the state and the user's described problem.
5. Propose a solution (clearly marked as AI interpretation).
6. If unresolved, create a ticket.
7. Prefill the technical context into the ticket.
8. Leave the user to confirm or modify before submission (never auto-submit).

**Invariants**: bounded to the user's permissions; never auto-submits; never exposes data the user may
not see; AI failure falls back to manual ticket creation.

### Support-Related Domain Events

Names aligned with the Event Model; each carries actor/context, subject reference, metadata, version.

- `ticket.created`, `ticket.updated`, `ticket.assigned`, `ticket.resolved`, `ticket.reopened`
- `incident.created`, `incident.updated`, `incident.resolved` (referenced; surfaced here)
- `feedback.created`, `feedback.converted` (to contribution/ticket/proposal/project, with provenance)
- `support.ai_diagnosis_performed` (records that AI assisted; no auto-submit)

### Key Entities

- **Ticket**: An individual user issue with type, custom fields, tags, state, workflow, assignment,
  attachments, requester, and history.
- **Ticket Type**: A category with its own custom-field schema and workflow.
- **Custom Field / Tag**: Structured data and triage labels on tickets.
- **Workflow / Transition**: The allowed states and moves for a ticket type.
- **Assignment**: The support agent responsible for a ticket.
- **Attachment**: A validated/sanitized file associated with a ticket/feedback.
- **Incident (referenced)**: A systemic problem surfaced to reduce duplicate tickets; distinct lifecycle.
- **Feedback**: A structured opinion/information submission (general, bug report, feature request).
- **Feedback Conversion**: An explicit, provenance-preserving hand-off of feedback to a contribution/
  ticket/feature proposal/community project in its owning domain.
- **AI Diagnosis Session**: A bounded, permission-respecting assistance that may prefill a ticket for user
  confirmation.
- **Support Role / Permission (referenced)**: Triage/assignment/transition rights (Permission Model).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Incident, Ticket, and Feedback are conflated in data/UI/logic in 0% of cases; each retains
  its own lifecycle.
- **SC-002**: Tickets are created without required custom fields in 0% of cases; invalid workflow
  transitions succeed in 0% of cases.
- **SC-003**: A known incident is surfaced to a user starting a related ticket in 100% of applicable
  cases (duplicate-reduction).
- **SC-004**: The AI auto-submits a ticket without user confirmation in 0% of cases; a prefilled ticket
  awaits confirmation in 100% of AI-created cases.
- **SC-005**: AI diagnosis accesses data the requesting user may not see in 0% of cases; AI failure blocks
  manual ticket creation in 0% of cases.
- **SC-006**: Feedback is auto-converted to a ticket without an explicit action in 0% of cases; every
  conversion preserves provenance in 100% of cases.
- **SC-007**: Feedback conversions create the target in its owning domain (not a Support-local clone) in
  100% of cases; contribution grants go through Gamification in 100% of cases.
- **SC-008**: Attachments execute unsafe content or expose secrets in 0% of cases.
- **SC-009**: A requester's private ticket data is exposed beyond the requester/permitted staff in 0% of
  cases.
- **SC-010**: 100% of sensitive support actions (cross-user reassignment, closing another's ticket,
  restricted-content access, conversions) produce an audit entry.

## Assumptions

- The AI engine and its provider abstraction are owned by the AI spec; Support invokes it for diagnosis
  within the user's permissions.
- The Wiki is owned by Content; Services & Health owns service state; Support consumes both.
- Incident and Maintenance full lifecycles are shared with Services & Health/Calendar; Support surfaces
  incidents and owns tickets/feedback.
- Community/Marketplace own feature proposals and community projects; Gamification owns Contribution;
  Support only converts/hands off with provenance.
- The exact per-type workflows, custom-field schemas, and attachment limits/types are configurable
  administrative data. (Flagged as OQ-75/OQ-77.)
- "Support roles" (Support, Moderator) come from the Permission Model; the exact split of support
  permissions is confirmed there. (Flagged as OQ-76.)

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation.

- **OQ-75 (Baseline workflows)**: Confirm the default ticket workflows per type (states/transitions) and
  whether admins can define custom workflows.
- **OQ-76 (Support permission split)**: Confirm which support actions require which role (Support vs
  Moderator vs Admin), especially cross-user operations and conversions.
- **OQ-77 (Attachment policy)**: Confirm allowed attachment types/sizes and the sanitization/retention
  policy, consistent with Privacy.
- **OQ-78 (Feedback→contribution rules)**: Confirm when feedback qualifies for a Contribution grant and
  how anti-abuse applies (to avoid farming via feedback), aligned with Gamification.
- **OQ-79 (Incident↔ticket linking/merge)**: Confirm the policy for linking/merging duplicate tickets to
  an incident and whether mass-updates to linked tickets are permitted.

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference) and the project
  Constitution (v1.0.0).
- Composes with: `specs/003-roles-permissions/spec.md` (`tickets.create`/`tickets.manage`; support roles;
  audit), `specs/006-services-health/spec.md` (service state for diagnosis; incident distinction),
  `specs/007-events-history/spec.md` (support events, provenance), `specs/008-search-command-palette/spec.md`
  (AI diagnosis; searchable tickets/incidents), `specs/010-notifications/spec.md` (support
  communications), `specs/011-content-news-wiki-calendar/spec.md` (Wiki knowledge; contextual help),
  `specs/012-community/spec.md` (feature proposal/community project conversion), and
  `specs/013-gamification-economy/spec.md` (contribution grants).
- Depends on / references: `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`,
  `ux/USER_JOURNEYS.md`, `architecture/EVENT_MODEL.md`, `architecture/DATA_MODEL.md`.
- Related specs (not owned here): the AI spec (engine/provider abstraction), Services & Health/Calendar
  (incident/maintenance lifecycles), Community/Marketplace (proposals/projects), Gamification
  (Contribution), and the Privacy spec (021) (visibility engine).
