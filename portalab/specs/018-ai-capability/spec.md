# Feature Specification: AI Capability

**Feature Branch**: `018-ai-capability`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Detailed functional specification of the AI Capability — a cross-cutting capability, not an isolated module."

## Role of This Document

This is a **detailed feature specification** for the AI Capability — a transversal ability (not a
module) that can understand, search, navigate, advise, and act across the portal, always within the
current user's permissions. It conforms to and refines the superior reference specification
(`specs/001-portal-global-spec/spec.md`) and composes with Roles & Permissions
(`specs/003-roles-permissions/spec.md`), the Portal Core shell (`specs/004-portal-core-shell/spec.md`),
Connectors (`specs/005-connectors/spec.md`), Events & History (`specs/007-events-history/spec.md`),
Search & Command Palette (`specs/008-search-command-palette/spec.md`), Content/Wiki
(`specs/011-content-news-wiki-calendar/spec.md`), Support (`specs/016-support/spec.md`), and Statistics
(`specs/017-statistics/spec.md`), under the project Constitution (`.specify/memory/constitution.md`,
v1.0.0). It draws on `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`, and
`architecture/PERMISSION_MODEL.md`.

Scope boundary: this spec **owns** the AI capability's behavior contract — what it can do
(understand/search/navigate/advise/act), the permission-boundedness, the sensitive-action confirmation
rule, source attribution, the parallel/non-blocking relationship with classic features, and the
treatment of MCParr as an **optional** external access/action layer. It **consumes** every domain it
reaches (Wiki, Search, Media, Statistics, Gamification, Calendar, News, Services, Health, Tickets,
Community, Marketplace, Connectors, history) through those domains' permissioned contracts; it does
**not** own them. It explicitly **chooses no AI model, provider, or technology** (a provider
abstraction is required, but no concrete choice is made here). It contains no implementation detail.

### Non-Negotiable AI Boundaries (normative)

- The AI **NEVER** has more permissions than the current user.
- The AI **NEVER** bypasses permissions or privacy; every access/action goes through the same
  server-side, deny-by-default authorization as a human action.
- **Sensitive actions require explicit user confirmation** where appropriate (deletion, permission
  changes, significant refunds, economy-rule changes, destructive service/data actions, etc.).
- The AI is a **cross-cutting capability**, reachable everywhere (per the shell), not an isolated module.
- Responses **should indicate the sources used** and distinguish real data, historical information, and
  interpretation.
- **MCParr** is an **optional** external access/action layer, **not** a mandatory functional dependency;
  the portal and the AI remain fully functional without it.

**Terminology**: Capability = functional ability; MCParr = an optional external access/action layer
(e.g., an MCP-style bridge) usable when present; Domain Event = a recorded fact.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - AI reachable everywhere, operating under the user's permissions (Priority: P1)

From anywhere in the portal, a user invokes the AI; it operates strictly under that user's effective
permissions — it can reach only what the user can reach, and never more.

**Why this priority**: The permission-bounded, cross-cutting nature is the defining and highest-risk
property; everything else depends on it being correct.

**Independent Test**: As users with different permissions, ask the AI the same question touching a
restricted area; confirm each AI answer reflects only what that user may access, and that the AI never
returns data the user could not otherwise see.

**Acceptance Scenarios**:

1. **Given** a user with limited permissions, **When** they ask the AI about a restricted resource,
   **Then** the AI returns only what the user may access and does not reveal restricted data.
2. **Given** the AI is invoked from different surfaces (shell, search, a detail page), **When** used,
   **Then** it is reachable everywhere and behaves as one cross-cutting capability.
3. **Given** two users with different rights, **When** they ask the same question, **Then** the answers
   differ exactly according to their respective permissions.

### User Story 2 - Understand, search, synthesize with source attribution (Priority: P1)

A user asks a question; the AI understands intent, searches permitted sources in parallel with classic
search, synthesizes an answer, and indicates which sources it used while distinguishing real data from
interpretation.

**Why this priority**: Understanding/searching/synthesizing with attribution is the primary value and
encodes the locked parallel-with-search and distinguish-real-vs-interpretation rules.

**Independent Test**: Ask a question spanning Wiki + Statistics; confirm classic results are not blocked,
the AI synthesis appears in parallel, cites the sources used, and marks interpretation distinctly from
real data.

**Acceptance Scenarios**:

1. **Given** a question, **When** the AI answers, **Then** classic search is not blocked and the AI works
   in parallel (per Search & AI independence).
2. **Given** an AI answer, **When** presented, **Then** it indicates the sources used and distinguishes
   real/historical data from interpretation/inference.
3. **Given** the AI lacks access to a source, **When** answering, **Then** it does not use it and does not
   fabricate data from it.

### User Story 3 - Navigate and explain (Priority: P2)

The AI can navigate the user to the right place (page/object/action) and explain how something works or
what a piece of data means, within permissions.

**Why this priority**: Navigation and explanation turn the AI into a guide across the one-environment,
reinforcing usability.

**Independent Test**: Ask the AI to take you to a specific permitted area and to explain a concept/
metric; confirm it navigates correctly (only to permitted destinations) and explains clearly, citing
sources where relevant.

**Acceptance Scenarios**:

1. **Given** a navigation request, **When** the AI acts, **Then** it navigates to a permitted
   destination (and refuses/omits unpermitted ones).
2. **Given** an explanation request, **When** answered, **Then** the explanation is grounded in permitted
   sources and marks interpretation distinctly.

### User Story 4 - Advise, diagnose, recommend (Priority: P2)

The AI can advise and diagnose (e.g., a service problem) and produce recommendations, grounded in
permitted data (Services/Health, Wiki, Statistics, history) and clearly marked as advice.

**Why this priority**: Advising/diagnosing/recommending is a core explicit ability and the basis of
AI-assisted support and discovery.

**Independent Test**: Trigger a diagnosis on a permitted service issue and ask for a recommendation;
confirm the advice is grounded in permitted data, marked as AI advice, and never exposes restricted
data.

**Acceptance Scenarios**:

1. **Given** a permitted service issue, **When** the AI diagnoses, **Then** it uses permitted
   Services/Health/Wiki/history data and proposes a solution marked as advice. The **AI-assisted ticket
   diagnosis workflow is owned by Support (016 / CD-018)**; this spec references that workflow and does
   not define a competing one.
2. **Given** a recommendation request, **When** answered, **Then** recommendations are grounded in
   permitted data and never surface another user's private data by permission alone.

### User Story 5 - Act: create/modify authorized objects and perform authorized actions (Priority: P1)

The AI can create/modify objects and perform actions **only** where the user is authorized; sensitive
actions require explicit user confirmation before execution.

**Why this priority**: Acting is the highest-impact ability; it must never exceed the user and must gate
sensitive operations behind confirmation.

**Independent Test**: Ask the AI to perform a permitted non-sensitive action (succeeds), a permitted
sensitive action (requires explicit confirmation before execution), and an unpermitted action (refused
server-side).

**Acceptance Scenarios**:

1. **Given** a permitted non-sensitive action, **When** the AI performs it, **Then** it succeeds under
   the user's permissions and is recorded/audited like a human action.
2. **Given** a sensitive action, **When** the AI would perform it, **Then** explicit user confirmation is
   required before execution; without confirmation it is not performed.
3. **Given** an action the user is not permitted to perform, **When** the AI attempts it, **Then** it is
   refused server-side exactly as a human attempt would be.
4. **Given** any AI-performed action, **When** executed, **Then** it obeys the same business rules,
   events, and audit as the equivalent human action (no parallel path).

### User Story 6 - Access domains via permissioned contracts (Priority: P1)

The AI reaches Wiki, Search, Media, Statistics, Gamification, Calendar, News, Services, Health, Tickets,
Community, Marketplace, Connectors, and history — each via that domain's permissioned contract — never
through a back door.

**Why this priority**: The breadth of reach is explicit, but each access must go through the same gates
as the rest of the portal.

**Independent Test**: For each listed domain, have the AI retrieve/act on permitted data and confirm it
is denied for unpermitted data; confirm access uses the domain's contract (not a privileged bypass).

**Acceptance Scenarios**:

1. **Given** each listed domain, **When** the AI accesses it, **Then** access is gated by that domain's
   permissions/privacy exactly as for a human.
2. **Given** a domain the user cannot access, **When** the AI tries, **Then** it is denied (no back
   door).
3. **Given** AI access to history, **When** used, **Then** historized ≠ public is honored and privacy is
   respected.

### User Story 7 - MCParr as an optional access/action layer (Priority: P2)

When MCParr is present, the AI may use it as an external access/action layer (still bounded by the user's
permissions and confirmation rules); when absent, the AI and portal remain fully functional.

**Why this priority**: MCParr must be treated as optional, not a mandatory dependency; mishandling would
couple the portal to an external layer.

**Independent Test**: With MCParr present, confirm the AI can use it within permissions and confirmation
rules; with MCParr absent, confirm the AI and all portal functions still work (nothing breaks).

**Acceptance Scenarios**:

1. **Given** MCParr is present, **When** the AI uses it, **Then** actions/access through MCParr are still
   bounded by the user's permissions and sensitive-action confirmation.
2. **Given** MCParr is absent, **When** the AI and portal are used, **Then** everything remains fully
   functional (MCParr is not a required dependency).
3. **Given** MCParr fails or is unavailable, **When** the AI operates, **Then** it degrades gracefully to
   non-MCParr capabilities without breaking unrelated functions.

### User Story 8 - Resilience: AI failure never breaks classic functions (Priority: P1)

If the AI is slow, unavailable, or errors, classic (non-AI) functions — search, navigation, actions —
remain fully usable.

**Why this priority**: "AI failure must not break classic functions" is a locked rule and a resilience
cornerstone.

**Independent Test**: Disable/slow the AI; confirm classic search, navigation, and manual actions remain
fully usable, and the AI surface shows a clear, non-blocking state.

**Acceptance Scenarios**:

1. **Given** the AI is unavailable, **When** the user uses the portal, **Then** classic functions remain
   fully usable and the AI shows a clear unavailable state.
2. **Given** the AI errors mid-task, **When** it fails, **Then** no unrelated function is broken and no
   partial sensitive action is performed without confirmation.
3. **Given** a provider is unavailable, **When** configured with a provider abstraction, **Then** the
   capability is not bound to a single concrete provider (graceful handling).

### Edge Cases

- **Prompt asks for restricted data**: The AI refuses/omits it exactly as the user would be denied;
  it never reveals data the user cannot access, and does not reveal the existence of restricted items
  where that existence is itself sensitive.
- **Prompt-injection via content**: Content the AI reads (e.g., a Wiki page, a ticket, external data)
  MUST NOT be able to escalate the AI's permissions or make it bypass authorization/confirmation.
- **Sensitive action without confirmation**: The AI never executes a sensitive action without explicit
  user confirmation; a timeout/absence of confirmation means no execution.
- **AI "thinks" it can act beyond the user**: Every action is re-authorized server-side; the AI's
  intent never overrides the authorization decision.
- **Fabrication / hallucination**: The AI distinguishes real/historical data from interpretation; it
  does not present invented data as real, and indicates sources used.
- **MCParr absent/failed**: The AI degrades to non-MCParr capabilities; nothing breaks; MCParr is never
  assumed present.
- **MCParr action exceeds user rights**: Refused — MCParr access/action is still bounded by the user's
  permissions and confirmation rules.
- **AI unavailable**: Classic functions fully usable; AI surface shows a non-blocking state.
- **Source unavailable mid-answer**: The AI indicates partial/uncertain results rather than fabricating;
  attribution reflects what was actually used.
- **Privacy in synthesis**: An aggregate/synthesized answer never de-anonymizes or exposes another
  user's private data by permission alone.
- **Audit of AI actions**: AI-performed sensitive actions are audited identically to human ones, with the
  AI noted as the acting channel on behalf of the user.
- **Secrets**: The AI never exposes secrets/credentials in answers or actions.

## Requirements *(mandatory)*

### Functional Requirements

#### Permission Boundaries (non-negotiable)
- **FR-001**: The AI MUST operate strictly under the current user's effective permissions and MUST NEVER
  have or gain more permissions than that user.
- **FR-002**: The AI MUST NEVER bypass authorization or privacy; every access and action MUST pass the
  same server-side, deny-by-default gates as a human action.
- **FR-003**: Content the AI reads MUST NOT be able to escalate its permissions or cause it to bypass
  authorization/confirmation (resistant to prompt-injection via data).
- **FR-004**: The AI MUST NOT reveal data the user cannot access, nor the existence of restricted items
  where that existence is itself sensitive.

#### Cross-Cutting Reach
- **FR-005**: The AI MUST be reachable everywhere in the portal (via the shell), behaving as one
  cross-cutting capability, not an isolated module.
- **FR-006**: The AI MUST access each domain — Wiki, Search, Media, Statistics, Gamification, Calendar,
  News, Services, Health, Tickets, Community, Marketplace, Connectors, and history — via that domain's
  permissioned contract, never a privileged back door.
- **FR-007**: AI access to history MUST honor "historized ≠ public" and privacy.

#### Capabilities: Understand / Search / Synthesize / Explain / Navigate / Advise / Diagnose
- **FR-008**: The AI MUST be able to understand user intent and search permitted sources, running in
  parallel with classic search without blocking it (per Search & AI independence).
- **FR-009**: The AI MUST be able to synthesize and explain, grounding answers in permitted sources.
- **FR-010**: The AI MUST be able to navigate the user to permitted destinations and MUST refuse/omit
  unpermitted ones.
- **FR-011**: The AI MUST be able to advise, diagnose, and recommend, grounded in permitted data and
  clearly marked as advice/interpretation. For support tickets, the AI MUST follow the **ticket
  diagnosis workflow owned by Support (016 / CD-018)** and MUST NOT define a competing workflow.

#### Capabilities: Act (create/modify/perform)
- **FR-012**: The AI MUST be able to create/modify authorized objects and perform authorized actions
  only where the user is permitted; unpermitted actions MUST be refused server-side.
- **FR-013**: Sensitive actions (deletion, permission changes, significant refunds, economy-rule changes,
  destructive service/data actions, and others classified sensitive) MUST require explicit user
  confirmation before the AI executes them.
- **FR-014**: Absence or timeout of confirmation MUST result in no execution of the sensitive action.
- **FR-015**: Any AI-performed action MUST obey the same business rules, emit the same events, and be
  audited the same as the equivalent human action (no parallel path), with the AI recorded as the acting
  channel on behalf of the user.

#### Source Attribution & Honesty
- **FR-016**: AI responses SHOULD indicate the sources used and MUST distinguish real/historical data
  from interpretation/inference.
- **FR-017**: The AI MUST NOT present invented/unverified data as real; where results are partial or
  uncertain, it MUST indicate so rather than fabricate.
- **FR-018**: The AI MUST NEVER expose secrets or credentials in responses or actions.

#### MCParr (optional external layer)
- **FR-019**: MCParr MUST be treated as an optional external access/action layer, NOT a mandatory
  functional dependency; the portal and AI MUST remain fully functional when MCParr is absent.
- **FR-020**: When MCParr is present and used, access/actions through it MUST still be bounded by the
  user's permissions and the sensitive-action confirmation rule.
- **FR-021**: If MCParr is unavailable or fails, the AI MUST degrade gracefully to non-MCParr
  capabilities without breaking unrelated functions.

#### Resilience & Provider Abstraction
- **FR-022**: An AI failure/unavailability MUST NOT break classic (non-AI) functions; the AI surface MUST
  show a clear, non-blocking state.
- **FR-023**: The AI capability MUST be defined against a provider abstraction so it is not bound to a
  single concrete model/provider (no model/provider is chosen in this spec).
- **FR-024**: An AI error mid-task MUST NOT leave a partial sensitive action performed without
  confirmation, and MUST NOT corrupt data.

#### Events, Audit, Privacy
- **FR-025**: AI-assisted and AI-performed actions MUST be observable; sensitive ones MUST be audited with
  actor (user), channel (AI), action, timestamp, context, decision/result.
- **FR-026**: AI interactions MAY emit domain events for history/statistics within privacy rules;
  consumers MUST be idempotent where duplicates are possible, and no secrets MUST be stored in events.
- **FR-027**: AI synthesis/aggregation MUST NOT de-anonymize or expose another user's private data by
  permission alone.

### AI Capability Model

**Abilities**: Understand → Search → Navigate → Advise/Diagnose → Act. Each is permission-bounded and,
for acting, confirmation-gated when sensitive.

**Access surface** (all via permissioned domain contracts): Wiki, Search, Media, Statistics,
Gamification, Calendar, News, Services, Health, Tickets, Community, Marketplace, Connectors, history, and
— when present — MCParr (optional).

**Invariants**:
- AI permissions == a subset of the current user's permissions (never a superset).
- Every access/action re-authorized server-side; intent never overrides authorization.
- Sensitive actions require explicit confirmation; no confirmation → no execution.
- Responses attribute sources and separate real data from interpretation.
- MCParr optional; AI/portal fully functional without it.
- AI failure never breaks classic functions.

### Action Confirmation Model

- **Non-sensitive authorized action**: AI may perform directly (audited like a human action).
- **Sensitive authorized action**: AI prepares it and MUST obtain explicit user confirmation before
  execution; the user may modify or cancel.
- **Unauthorized action**: refused server-side regardless of AI intent.

### AI-Related Domain Events (illustrative)

- `ai.query_performed` (within privacy), `ai.action_prepared`, `ai.action_confirmed`,
  `ai.action_performed` (mirrors the underlying domain event), `ai.diagnosis_performed` (see Support).

### Key Entities

- **AI Capability**: The transversal ability to understand/search/navigate/advise/act, bounded by the
  user's permissions.
- **AI Session/Interaction**: A bounded, permission-scoped exchange; records sources used and any
  actions prepared/performed.
- **Source Reference**: An attribution to a permitted source used in an answer (Wiki page, statistic,
  history entry, etc.).
- **Prepared Action**: A pending AI-prepared action awaiting user confirmation (for sensitive actions).
- **Provider Abstraction (referenced)**: The interface decoupling the capability from any concrete
  model/provider (no choice made here).
- **MCParr Layer (optional, referenced)**: An external access/action layer usable when present, bounded
  by permissions/confirmation.
- **Permission/Privacy/Audit/Event engines (referenced)**: Gates and records the AI composes with.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The AI returns or acts on data/actions beyond the current user's permissions in 0% of
  cases.
- **SC-002**: The AI bypasses an authorization/privacy gate in 0% of cases (every access/action
  re-authorized server-side).
- **SC-003**: A sensitive action is executed by the AI without explicit user confirmation in 0% of cases.
- **SC-004**: AI responses indicate the sources used in 100% of answers that draw on sources, and
  distinguish real data from interpretation in 100% of answers.
- **SC-005**: Classic functions remain fully usable when the AI is unavailable in 100% of cases.
- **SC-006**: The portal and AI remain fully functional with MCParr absent in 100% of cases (MCParr is a
  hard dependency in 0% of cases).
- **SC-007**: MCParr-mediated access/actions exceed the user's permissions or skip confirmation in 0% of
  cases.
- **SC-008**: AI-performed actions are audited identically to human actions (with AI noted as channel) in
  100% of sensitive cases.
- **SC-009**: The AI presents invented/unverified data as real in 0% of cases; partial/uncertain results
  are indicated in 100% of such cases.
- **SC-010**: AI synthesis de-anonymizes or exposes another user's private data by permission alone in 0%
  of cases.

## Assumptions

- No AI model, provider, or technology is chosen here; a provider abstraction is required so the
  capability is not bound to one provider. (Flagged as OQ-85.)
- Each reachable domain owns its data and exposes permissioned contracts; the AI consumes them and never
  gets a privileged bypass.
- The authorization, privacy, audit, event/history, and search engines are owned by their specs; the AI
  composes with them.
- MCParr is an optional external MCP-style access/action layer specific to the operator's environment; it
  is never assumed present. (Flagged as OQ-87.)
- The exact set of "sensitive" actions is at least the Constitution/Permissions set; detailed domains may
  mark more. (Flagged as OQ-86.)

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation.

- **OQ-85 (Provider abstraction boundary)**: Confirm the functional expectations of the provider
  abstraction (capabilities required, fallback behavior) without choosing a model/provider.
- **OQ-86 (Sensitive-action catalog for AI)**: Confirm the exact set of actions requiring explicit
  confirmation when AI-initiated, aligned with Roles & Permissions (OQ-13/14) and each domain.
- **OQ-87 (MCParr scope & trust)**: Confirm what MCParr may access/do when present, how its permission
  mapping to the portal user works, and its trust boundary.
- **OQ-88 (Source-attribution granularity)**: Confirm how precisely sources must be cited (per claim vs
  per answer) and how interpretation is visually/again distinguished.
- **OQ-89 (AI action audit detail)**: Confirm the audit detail for AI-performed actions (how the AI
  channel, prompt provenance, and confirmation are recorded) consistent with privacy (no secret/PII
  leakage into audit).

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference) and the project
  Constitution (v1.0.0).
- Composes with: `specs/003-roles-permissions/spec.md` (`ai.use`; deny-by-default gating; sensitive-action
  confirmation/audit), `specs/004-portal-core-shell/spec.md` (AI reachable everywhere; non-blocking),
  `specs/005-connectors/spec.md` (Connectors access via capabilities), `specs/007-events-history/spec.md`
  (history access; AI events; idempotency), `specs/008-search-command-palette/spec.md` (parallel search/AI),
  `specs/016-support/spec.md` (AI diagnosis flow), and `specs/017-statistics/spec.md` (statistics as a
  permitted source/consumer).
- Depends on / references: `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`,
  `architecture/PERMISSION_MODEL.md`, `architecture/EVENT_MODEL.md`.
- Related specs (not owned here): every reachable domain (Wiki/Media/Calendar/News/Services/Health/
  Tickets/Community/Marketplace/Gamification), the Privacy spec (021) (visibility/anonymization), and the optional
  MCParr layer (external).
