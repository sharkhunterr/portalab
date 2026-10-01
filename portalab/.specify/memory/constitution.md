<!--
SYNC IMPACT REPORT
==================
Version change: (unfilled template) → 1.0.0
Bump rationale: Initial ratification. The previous file was the unpopulated Spec Kit
template (all [PLACEHOLDER] tokens). This is the first concrete constitution for the
Personal Extensible Portal, so it is adopted at 1.0.0.

Principles (all added — 20 total):
  I.    Product Integrity
  II.   Modular Architecture
  III.  Extensibility First
  IV.   Event-Driven Domain
  V.    Source of Truth & Data Integrity
  VI.   Security & Authorization
  VII.  Privacy by Design
  VIII. Testability & Quality
  IX.   Resilience & Graceful Degradation
  X.    UX Consistency
  XI.   Functional State vs Presentation
  XII.  Accessibility
  XIII. Observability & Auditability
  XIV.  Deterministic Business Rules
  XV.   Internal Economy Integrity
  XVI.  AI Safety & Boundaries
  XVII. Search and AI Independence
  XVIII.Configuration Hierarchy
  XIX.  Versioning & Evolution
  XX.   Simplicity & Maintainability

Added sections: Core Principles (I–XX); Governance.
Removed sections: None (template placeholders replaced).

Templates requiring updates:
  ✅ .specify/templates/plan-template.md — Constitution Check gates made concrete.
  ✅ .specify/templates/spec-template.md — reviewed; mandatory requirement areas already
     compatible (permissions, events, privacy, degraded mode, acceptance criteria).
  ✅ .specify/templates/tasks-template.md — reviewed; task categories cover testing,
     observability, and extensibility-driven work; no structural change required.
  ✅ .claude/CLAUDE.md (project root) — reviewed; git identity rules unaffected.

Deferred items / TODOs: None. Ratification date = project current date (2026-10-01);
no earlier historical adoption date exists.
-->

# Personal Extensible Portal Constitution

The Personal Extensible Portal is a technology-agnostic experience layer above connected
services. This Constitution defines the non-negotiable principles that every future
specification, plan, task, and implementation MUST obey. It governs **how** the product is
built; it does not redefine **what** the product is — that remains the authority of
`product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`, and `decisions/DECISIONS.md`.

Where this Constitution and those product documents appear to conflict, the conflict MUST be
raised and resolved explicitly (see Governance); it MUST NOT be silently resolved in code.

## Core Principles

### I. Product Integrity

Implemented behavior MUST remain faithful to the Product Blueprint, Business Rules, and
locked Decisions.

- Business rules MUST NOT be weakened, removed, or reinterpreted to make implementation
  easier, faster, or simpler.
- Any material contradiction discovered between code, specifications, and the product
  documents MUST be surfaced to a human and recorded; it MUST NOT be resolved silently.
- When the product documents are genuinely silent on a decision, the gap MUST be flagged as
  an open question rather than invented. Missing product decisions MUST NOT be inferred
  silently.

*Rationale: The product documentation is the single source of functional truth; drift
between intent and implementation is the most expensive failure mode for this project.*

### II. Modular Architecture

The architecture MUST preserve clear separation between Portal Core, Modules, Plugins,
Connectors, Services, and Capabilities.

- A Module MUST depend on Capabilities (functional contracts), not on a particular external
  Service, whenever a capability abstraction is possible.
- Adding a new Service MUST be primarily additive: it MUST NOT require rewriting existing
  Modules.
- The Core MUST NOT depend on any optional Module or Plugin to remain functional.

*Rationale: Capability-based integration is the product's core differentiator and the
mechanism that lets the system evolve without rewriting the core.*

### III. Extensibility First

Extensibility is a foundational architectural property, not an afterthought.

- A Plugin MUST be able to: add features, add pages, enrich existing pages, enrich existing
  objects, add widgets, consume events, produce events, and declare permissions.
- Disabling a Plugin MUST NOT automatically delete its data.
- A Plugin failure MUST NOT break unrelated portal functions.
- The Core and every Module MUST remain functional when optional Plugins are absent.
- New capability MUST prefer existing extension points (capabilities, events, history,
  permissions, configuration, design system) over parallel isolated mechanisms.

*Rationale: The portal must grow without a rewrite; isolated one-off mechanisms erode that
guarantee.*

### IV. Event-Driven Domain

Events and history are a cross-cutting backbone of the portal.

- Features MUST be able to react to events without directly depending on the service that
  produced them.
- Event consumers MUST be idempotent wherever duplicate delivery is possible.
- An event's occurrence timestamp MUST represent the real occurrence time (`occurred_at`),
  distinct from portal receipt time (`received_at`).
- History MUST retain the provenance and context required by the features that consume it.

*Rationale: Decoupling producers from consumers via durable, idempotent events is what keeps
features independent and the product loop reliable.*

### V. Source of Truth & Data Integrity

Every piece of data MUST have a clearly defined source of truth.

- External services remain the authoritative owners of their native data.
- The portal MUST store only the representations and history its own features require.
- A synchronization run or a service outage MUST NOT silently destroy portal history.
- A full resync MUST NOT blindly destroy native portal data; conflicting sources MUST follow
  configured source-of-truth rules or preserve provenance.
- Data migrations and transformations MUST preserve historical integrity.
- Sync state and service health are distinct and MUST be representable independently.

*Rationale: Trust in the portal collapses if historized data can vanish or be silently
overwritten by an upstream hiccup.*

### VI. Security & Authorization

Authorization MUST follow Default Deny.

- Every action MUST be authorized server-side according to the user's effective context.
- Permissions MUST NEVER be enforced only in the UI.
- The AI MUST operate with exactly the permissions of the user it represents and MUST NEVER
  bypass an authorization check.
- Sensitive actions (deletion, permission changes, significant refunds, economy-rule
  changes, destructive service/data actions) MUST be confirmed where appropriate and MUST be
  audited.
- Secrets MUST NEVER be exposed to the client unnecessarily.

*Rationale: Server-side, deny-by-default authorization is the only trustworthy boundary;
client-side checks are advisory at best.*

### VII. Privacy by Design

Privacy is independent from functional permission.

- Historized data MUST NOT be treated as automatically public.
- User visibility preferences (Public, Community, Leaderboard-only, Private) MUST be honored
  within the bounds of administrative policy.
- An administrative visibility override MUST preserve the user's underlying preference and
  MUST restore it when the override is removed.
- Deletion or anonymization MUST preserve the integrity of aggregate and historical data
  where that data is non-identifying and necessary.

*Rationale: "Historized does not mean public" is a locked product decision; privacy and
permission are separate axes and must stay separate in code.*

### VIII. Testability & Quality

Every significant feature MUST be testable, and its specification's acceptance criteria MUST
be verifiable by tests.

- Tests MUST cover, where relevant: nominal behavior, errors, permissions, privacy, edge
  cases, synchronization, events, degraded mode, and extensibility.
- Code quality MUST NOT be sacrificed to accelerate an implementation.
- A specification whose acceptance criteria cannot be expressed as verifiable checks is
  incomplete and MUST be revised before implementation.

*Rationale: Unverifiable requirements cannot be governed; untested cross-cutting behavior is
where business-rule and permission regressions hide.*

### IX. Resilience & Graceful Degradation

The portal MUST remain usable when part of the system is unavailable.

- A slow or unavailable external service MUST NOT unnecessarily block unrelated
  functionality.
- The following functional states MUST be distinguishable when relevant: loading, available,
  partial, stale, error, unavailable, maintenance, unauthorized, no data, syncing.
- Stale data MAY be presented when it is available, but its staleness MUST be identifiable to
  the user.

*Rationale: A personal portal aggregating many services will routinely have some services
down; partial failure must stay partial.*

### X. UX Consistency

The portal MUST feel like one coherent environment, not a collection of links.

- Modules and Plugins MUST use the shared Design System principles and components.
- User journeys MUST avoid dead-ends (no dead-end empty states).
- Every important page MUST let the user understand: where they are, what they can do, what
  is happening, and what the relevant next action is.

*Rationale: Coherence is the product's promise; inconsistent surfaces break the "single
environment" experience that differentiates it.*

### XI. Functional State vs Presentation

Functional logic MUST be independent of its visual representation.

- A functional state MUST carry the same meaning regardless of theme or personalization.
- Themes and personalization MAY change appearance profoundly but MUST NOT change
  permissions, security, business rules, source-of-truth, or actual service state.
- Accessibility preferences MUST take priority over purely visual effects.

*Rationale: Themes change presentation, not functional truth; conflating the two would let
cosmetics alter behavior.*

### XII. Accessibility

Accessibility is cross-cutting across the entire product.

- Features MUST remain usable with: keyboard, touch, varying screen sizes, reduced motion,
  disabled sound, and contrast/legibility needs.
- Mobile MUST remain functionally complete, not a reduced subset.
- No visual personalization MUST EVER render critical information inaccessible.

*Rationale: Accessibility applied per-feature is applied nowhere; it must be a transversal
guarantee.*

### XIII. Observability & Auditability

Important operations MUST be observable, and sensitive actions MUST be auditable.

- An audit entry for a sensitive action MUST record at minimum: actor, action, timestamp,
  context, and result where relevant.
- The portal MUST be able to diagnose its own problems and those of connected services.
- Errors MUST be explainable and actionable rather than merely masking the failure.

*Rationale: Without audit trails and self-diagnosis, neither trust nor support (tickets,
incidents, AI diagnosis) can function.*

### XIV. Deterministic Business Rules

Business mechanisms — XP, Contribution, Coins, Achievements, Events/campaigns, Marketplace,
Funding, Automations — MUST produce deterministic, traceable, consistent results.

- Overlapping events/campaigns MUST resolve via deterministic configured rules; duplicate
  rewards MUST be prevented and anti-farming limits MUST apply.
- Economic transactions MUST NEVER be rewritten to alter history.
- Rules whose change could affect the interpretation of historical data MUST be versionable,
  and historical rewards/transactions MUST remain bound to the rule version in force when
  they occurred.

*Rationale: Gamification and economy lose all legitimacy if outcomes are non-reproducible or
history can be retroactively rewritten.*

### XV. Internal Economy Integrity

Coins are exclusively an internal virtual currency.

- Coins MUST NOT represent real money; the current product has no real-money coin purchases.
- Every Coin movement MUST be recorded as a traceable transaction.
- A Coin balance MUST normally never become negative; any exception MUST be an explicit,
  audited manual correction.
- Refunds MUST be represented as new transactions, never as retroactive edits of an existing
  transaction.
- On final account deletion, remaining Coins MUST be destroyed.

*Rationale: An auditable, append-only economy is a locked decision and the basis of
Marketplace and Funding trust.*

### XVI. AI Safety & Boundaries

The AI is a cross-cutting capability that MUST stay within human authorization boundaries.

- The AI MAY understand, search, explain, recommend, navigate, and perform authorized
  actions.
- The AI MUST NEVER become a path to bypass permissions; sensitive actions via AI MUST obey
  the same authorization rules as human-initiated actions.
- AI responses MUST allow distinguishing real data, historical information, and
  interpretation/inference.
- An AI failure MUST NOT break classic (non-AI) functions.

*Rationale: "AI never has more rights than the current user" is a locked principle; AI is a
lens over the product, not an escalation path.*

### XVII. Search and AI Independence

Classic search and AI MUST operate independently and in parallel.

- Classic search MUST NOT wait for the AI response to return results.
- An AI outage or unavailability MUST NOT render classic search unusable.
- A search failure MUST NOT prevent the AI from using the sources it legitimately has access
  to.

*Rationale: Parallel, non-blocking search and AI is a locked decision; coupling them would
make each a single point of failure for the other.*

### XVIII. Configuration Hierarchy

Configuration MUST follow a clear precedence: Global → Module → Plugin → User.

- Administrative policies MAY impose constraints at higher levels.
- User preferences MUST be retained wherever they remain permitted, even when temporarily
  overridden by policy.
- Defaults MUST yield a usable experience without excessive configuration.

*Rationale: A predictable configuration hierarchy keeps admin policy, plugin behavior, and
user choice composable instead of contradictory.*

### XIX. Versioning & Evolution

Significant functional changes MUST be versionable when they affect the interpretation of
historical data or transactions.

- Past transactions, purchases, rewards, terms acceptances, and historical events MUST NOT
  be arbitrarily reinterpreted by a new rule.
- Changes MUST preserve compatibility with existing workflows as far as reasonably possible;
  evolution MUST NOT break existing user workflows without explicit, documented justification.

*Rationale: The product is designed to evolve continuously; evolution that silently rewrites
the meaning of past data destroys auditability and user trust.*

### XX. Simplicity & Maintainability

The chosen solution MUST be as simple as possible while satisfying product requirements.

- Technology, abstraction, or infrastructure MUST NOT be introduced solely because it is
  available; each addition MUST be justified by a product requirement.
- Cross-cutting mechanisms MUST NOT be duplicated.
- Reusable components and clearly defined contracts MUST be preferred over bespoke parallel
  implementations.

*Rationale: Simplicity is what keeps an extensible, event-driven, multi-module system
maintainable over its long evolutionary life.*

## Governance

This Constitution is the authoritative reference for the project's development principles. It
governs specifications, plans, tasks, and implementations.

**Authority and precedence.**
- Specifications MUST comply with this Constitution.
- Technical plans MUST justify their choices against the requirements and the principles of
  this Constitution, and MUST record any deviation in a Complexity/Deviation tracking section
  with justification.
- Implementations MUST comply with their specifications and this Constitution.
- Where this Constitution conflicts with `product/PRODUCT_BLUEPRINT.md`,
  `product/BUSINESS_RULES.md`, or `decisions/DECISIONS.md`, the product documents prevail on
  **what** the product does; this Constitution prevails on **how** it is built. Genuine
  contradictions MUST be escalated to a human and resolved explicitly, never silently in code.

**Amendment procedure.**
- Any change to a core principle MUST be explicitly documented and versioned.
- Amendments MUST update the Sync Impact Report at the top of this file and propagate to
  dependent templates (`plan-template.md`, `spec-template.md`, `tasks-template.md`) and
  runtime guidance.

**Versioning policy (semantic).**
- MAJOR: backward-incompatible governance changes, or removal/redefinition of a principle.
- MINOR: a new principle/section is added, or guidance is materially expanded.
- PATCH: clarifications, wording, or non-semantic refinements.

**Compliance review.**
- Every specification and plan review MUST verify compliance with the applicable principles.
- Complexity or deviation from these principles MUST be justified in writing or the change
  MUST be simplified.

**Version**: 1.0.0 | **Ratified**: 2026-10-01 | **Last Amended**: 2026-10-01
