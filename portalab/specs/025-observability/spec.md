# Feature Specification: Observability

**Feature Branch**: `025-observability`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Complete functional specification of the portal's transversal Observability capability — the portal observing itself."

## Role of This Document

This is a **detailed feature specification** for Observability — the transversal capability that lets the
**portal observe itself**: whether the portal and its components, synchronizations, events, automations,
plugins, connectors, and AI are working; where errors occur, since when, with what impact, and what can be
done. It conforms to and refines the superior reference specification (`specs/001-portal-global-spec/spec.md`)
and **composes with** Roles & Permissions (`003`), Connectors (`005`), Services & Health (`006`), Events &
History (`007`), Search (`008`), Dashboard (`009`), Notifications (`010`), Support/Incidents (`016`), AI
(`018`), Automations (`019`), Administration (`020`), Privacy (`021`), and Extensibility (`023`), under the
project Constitution (`.specify/memory/constitution.md`, v1.0.0). It draws on
`product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`, `product/GLOSSARY.md`,
`architecture/FUNCTIONAL_ARCHITECTURE.md`, `architecture/EVENT_MODEL.md`, `architecture/DATA_MODEL.md`, and
`architecture/PERMISSION_MODEL.md`.

### What this spec OWNS vs CONSUMES (normative — no duplication, principle XX)

- **OWNS**: the **self-observation** of the portal — portal/technical/functional health model, events/
  sync/automation/plugin/connector/AI/performance observability views, the **structured error model**, the
  **Observation → Anomaly → Incident** escalation definition, the **admin observability dashboard**
  (action-first), observability history/trends and retention, and the **common observable-contribution
  model** for plugins/connectors.
- **CONSUMES (does not re-define, does not replace)**: service state/availability vs health vs sync →
  **Services & Health (006)** (Observability **completes**, never replaces it); the event/history backbone,
  `occurred_at`/`received_at`, dedup → **Events & History (007)**; the Incident lifecycle → **Support (016)**
  (no second incident system); alerting delivery → **Notifications (010)**; triggers/actions → **Automations
  (019)**; global search indexing → **Search (008)**; AI access within permissions → **AI (018)**;
  authorization → **Roles & Permissions (003)**; privacy/visibility/retention → **Privacy (021)**; plugin/
  connector contribution points → **Extensibility (023)**; the admin Control Center surface → **Administration
  (020)**.

**Non-goal**: Observability is **not limited to CPU/RAM metrics**, and MUST NOT become a dumping ground of
hundreds of raw metrics. It MUST NOT be a blocking dependency of the portal (degraded-mode rule, §DM).

**Terminology** (Glossary + prior specs): Observation = a recorded observable fact/measure; Anomaly = an
abnormal pattern detected from observations (not yet an incident); Incident = the systemic-problem record
owned by Support (016); Technical Health = "is it up/responding?"; Functional Health = "is it actually
doing its job?"; Domain Event = a recorded fact; `occurred_at` = real occurrence time.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Admin sees whether the portal and its components work (Priority: P1)

A privileged admin opens the observability dashboard and immediately understands global portal health,
which components (events, sync, automations, plugins, connectors, AI, background tasks) are healthy or
degraded, where errors occur, since when, with what impact, and what actions are available.

**Why this priority**: Self-observation is the reason this capability exists; the action-first overview is
its core deliverable.

**Independent Test**: As an admin, open the observability dashboard; confirm it shows global health,
active problems prioritized by required-action/impact/criticality/age, and that each component's health is
visible with "since when" and "impact" — not a wall of raw metrics.

**Acceptance Scenarios**:

1. **Given** the admin opens Observability, **When** it loads, **Then** it shows global portal health and
   the health of events, sync, automations, plugins, connectors, AI, and background tasks, each loading
   independently.
2. **Given** active problems exist, **When** the dashboard loads, **Then** they are ordered by
   required-action → impact → criticality → age → details (not a flat metric list).
3. **Given** a problem, **When** inspected, **Then** the admin can see where it occurs, since when, its
   impact, and the available diagnostic actions.

### User Story 2 - Technical health vs functional health distinction (Priority: P1)

The system distinguishes **technical health** (available/responding) from **functional health** (actually
doing its job); a component that is technically up but functionally degraded (e.g., sync no longer
completing) is shown as degraded.

**Why this priority**: This explicit distinction is the heart of the brief; conflating them hides real
failures behind "green" status.

**Independent Test**: Make a component technically up but functionally broken (e.g., a service reachable
but sync not completing, or events received but not processed); confirm technical health shows "up" while
functional health shows "degraded", distinctly.

**Acceptance Scenarios**:

1. **Given** a component reachable/responding but not performing its function, **When** observed, **Then**
   technical health shows available while functional health shows degraded — the two are distinct.
2. **Given** functional degradation (sync not completing, events not processed, notifications not sent,
   data abnormally stale, abnormal error rate), **When** detected, **Then** it is surfaced as a functional
   problem even if technical health is green.
3. **Given** both health axes, **When** displayed, **Then** neither is presented as the other.

### User Story 3 - Events, sync, automation observability (Priority: P1)

An admin observes the event system (received/processed/failed/ignored/duplicated/pending, processing time,
origin, reactions), synchronizations (last/next, duration, counts added/modified/removed/ignored/errored,
last error, state, data freshness), and automations (active rules, executions, success/failure, durations,
unmet conditions, actions performed/failed, loops detected, suspended rules + reasons).

**Why this priority**: These three engines are the backbone of the product loop; observing them is where
most functional failures are caught — and they reuse existing specs (007/005/019).

**Independent Test**: Exercise events (including a duplicate and a failure), a sync (success and error),
and an automation (success, failure, and auto-suspension); confirm each observability view reflects the
correct counts/states, that "service available ≠ sync functional" is distinguishable, and that a
loop-suspended automation is clearly identified.

**Acceptance Scenarios**:

1. **Given** the event system, **When** observed, **Then** received/processed/failed/ignored/duplicated/
   pending counts, processing time, origin, and reactions (where relevant) are visible (per permissions),
   without exposing private payload data.
2. **Given** a service's sync, **When** observed, **Then** last/next sync, duration, item counts (added/
   modified/removed-or-disabled/ignored/errored), last error, current state, and data freshness are
   visible; "service available" and "sync functional" are distinguishable; a failed sync has NOT deleted
   already-synced data (per 005).
3. **Given** the automation engine, **When** observed, **Then** active rules, executions, success/failure,
   durations, unmet conditions, actions performed/failed, detected loops, and suspended rules + reasons are
   visible; an auto-suspended (loop/repeat) automation is clearly identifiable (per 019).

### User Story 4 - Plugin & connector observability (Priority: P1)

Each plugin and connector exposes an observability state through a common model: active/disabled/error/
incompatible/invalid-config/missing-dependency, version, last activity, recent errors; connectors also show
state, last connection/sync, errors, latency, available data/capabilities — completing Services & Health.

**Why this priority**: Plugins/connectors are the main extensibility surface and a frequent failure point;
a failing one must be visible and must not take down the portal.

**Independent Test**: Induce a plugin error, an incompatible/invalid-config plugin, and a degraded
connector (service down vs auth invalid vs sync error vs stale); confirm each is distinctly observable via
the common model, and that a failing plugin/connector does not make the portal unavailable.

**Acceptance Scenarios**:

1. **Given** a plugin, **When** observed, **Then** its state (active/disabled/error/incompatible/invalid-
   config/missing-dependency), version, last activity, and recent errors are visible via the common model.
2. **Given** a failing plugin, **When** it fails, **Then** the portal remains available (isolation per 023)
   and the failure is observable.
3. **Given** a connector, **When** observed, **Then** state, last connection/sync, errors, latency,
   available data/capabilities, and last activity are visible, distinguishing connector-functional vs
   external-service-unavailable vs invalid-auth vs sync-error vs stale (completing 006, not replacing it).

### User Story 5 - AI observability without exposing private content (Priority: P1)

An admin observes the AI capability — requests, response time, errors, timeouts, provider availability,
model used, consumption where available, tools/connectors used, actions performed, failure rate — WITHOUT
the private content of conversations being exposed in stats/dashboards.

**Why this priority**: AI reliability must be observable, but AI conversations are sensitive; metadata-only
observation is a locked privacy expectation.

**Independent Test**: Generate AI activity (including an error/timeout); confirm the admin sees technical
metadata (counts, latency, errors, provider/model, tools used, actions, failure rate) while the private
conversation content is NOT exposed in observability surfaces.

**Acceptance Scenarios**:

1. **Given** AI activity, **When** observed, **Then** requests, response time, errors, timeouts, provider
   availability, model used, consumption (where available), tools/connectors used, actions performed, and
   failure rate are visible (per permissions).
2. **Given** AI conversations, **When** observability is viewed, **Then** their private content is NOT
   automatically exposed in stats/dashboards; only technical metadata is retained where needed.
3. **Given** AI actions, **When** observed, **Then** they are consistent with the AI's audited actions (018)
   and never reveal data beyond the viewer's permissions.

### User Story 6 - Performance observability with time attribution (Priority: P2)

The system identifies performance problems (slow pages/widgets/connectors/searches/AI/sync/automations) and
attributes time to portal-wait vs external-service-wait vs internal-processing vs timeout — without
imposing arbitrary technical thresholds here.

**Why this priority**: Performance problems are a top admin concern; attributing where time goes is what
makes them actionable, and it must not hard-code thresholds that depend on final architecture.

**Independent Test**: Induce slowness in a connector and in internal processing; confirm the system
attributes the delay to the correct bucket (external vs internal vs timeout) and surfaces the slow
component, without a hard-coded threshold baked into this spec.

**Acceptance Scenarios**:

1. **Given** a slow surface/component, **When** observed, **Then** it is identified and the time is
   attributed to portal-wait, external-service-wait, internal-processing, or timeout.
2. **Given** performance observation, **When** defined, **Then** this spec imposes no fixed technical
   threshold (thresholds are configurable/architecture-dependent — see OQ).
3. **Given** a slow external service, **When** attributed, **Then** the portal does not misreport it as an
   internal portal failure (and vice-versa).

### User Story 7 - Structured errors and the Observation → Anomaly → Incident escalation (Priority: P1)

Observed errors are structured (date, component/service/plugin/event, concerned user if relevant+permitted,
category, level, message, technical context, frequency, first/last occurrence, state, resolution); the
system can detect anomalies and escalate Observation → Anomaly → Incident per defined rules, feeding the
existing Incident system (no second incidents system).

**Why this priority**: Structured errors + a clear escalation model are what turn raw observation into
actionable, auditable incident management — reusing Support (016).

**Independent Test**: Produce repeated structured errors; confirm they carry the required fields; trigger
an anomaly (e.g., error-rate spike); confirm it is an Anomaly (not automatically an Incident); meet the
escalation rule and confirm an Incident is created in Support (016) with notifications, not in a separate
system.

**Acceptance Scenarios**:

1. **Given** an error, **When** recorded, **Then** it is structured with the relevant fields and is
   diagnosable (no generic un-diagnosable errors); secrets are never included.
2. **Given** abnormal behavior (error spike, abnormally long sync, repeated automation, blocked event,
   unstable service, latency spike, repeated failure), **When** detected, **Then** it is an **Anomaly**,
   which is NOT automatically an Incident.
3. **Given** an anomaly meeting the escalation rule, **When** evaluated, **Then** a potential incident is
   raised → validated automatically or by a human per rule → an **Incident is created in Support (016)** →
   notifications → tracking → resolution; no independent incident system is created.

### User Story 8 - Alerting and diagnostic actions via existing engines (Priority: P1)

Observability produces alerts (portal degraded, critical sync failure, suspended automation, connector
unavailable, critical storage, repeated error, AI unavailable) through the existing Notifications engine,
and offers contextual diagnostic actions (rerun sync/task, test connector, disable a problematic
automation, open docs, create/open incident, view history, ask the AI) — sensitive actions permissioned
and audited.

**Why this priority**: Alerts and actions are how observation becomes intervention; they must reuse
Notifications (010) and Automations (019) and obey permissions/audit, not create parallel mechanisms.

**Independent Test**: Trigger an alert condition and confirm it is delivered via Notifications respecting
preferences; from a problem, invoke a diagnostic action (e.g., rerun a sync, test a connector, disable an
automation); confirm it is permission-gated and audited.

**Acceptance Scenarios**:

1. **Given** an alert condition, **When** met, **Then** an alert is produced via the Notifications engine
   (010), respecting preferences/permissions — no separate notification mechanism.
2. **Given** a problem, **When** the admin uses a contextual diagnostic action (rerun sync/task, test
   connector, disable automation, open docs, create/open incident, view history, ask AI), **Then** it
   executes through the owning domain, and sensitive actions are confirmed and audited (003/020).
3. **Given** observability events, **When** they occur, **Then** they can drive the existing Automations
   (019) and Notifications (010) rules (observability is a trigger source, not a new engine).

### User Story 9 - Permissions & privacy for observability (Priority: P1)

Observability is primarily administrative/privileged; standard users do not by default access technical
logs, sensitive infrastructure info, detailed internal errors, other users' data, or anything revealing
secrets; Support and Admin may have different levels; privacy is never bypassed.

**Why this priority**: Observability is a prime vector for privacy/secret leakage; it must strictly obey
the Permission Model (003) and Privacy (021).

**Independent Test**: As a standard user, confirm no access to technical logs/infra/internal errors/others'
data/secrets; as Support vs Admin, confirm appropriately different levels; confirm no secret (token/
password/API key/OIDC) ever appears in logs/traces.

**Acceptance Scenarios**:

1. **Given** a standard user, **When** they attempt to access observability internals, **Then** access is
   denied by default (deny-by-default per 003).
2. **Given** Support vs Admin roles, **When** observability is accessed, **Then** each sees only its
   permitted level; user data is shown only when necessary, permitted, and justified (021).
3. **Given** logs/traces/errors, **When** recorded, **Then** they exclude secrets (tokens, passwords, API
   keys, OIDC secrets) and unnecessary sensitive data.

### User Story 10 - History, trends, and retention (Priority: P2)

Observability keeps history and trends (errors over time, availability, incidents, syncs, performance,
automations, plugins, AI) over adapted periods, with a configurable retention policy; detailed/voluminous
technical data may have a shorter retention than important business events, and observability history is
distinct from user functional data where needed.

**Why this priority**: Trends turn point-in-time observation into understanding; retention must avoid
indefinite hoarding of detailed technical data while preserving what matters.

**Independent Test**: Generate observability data over time; view trends over periods; confirm a retention
policy applies (detailed technical data expires sooner than important events), and that observability
history is separable from user functional data.

**Acceptance Scenarios**:

1. **Given** observability data, **When** viewed, **Then** errors/availability/incidents/syncs/performance/
   automations/plugins/AI trends are available over adapted periods.
2. **Given** retention policy, **When** applied, **Then** voluminous/detailed technical data MAY expire
   sooner than important business events; nothing is kept indefinitely without reason; policy is
   configurable where relevant.
3. **Given** observability history, **When** stored, **Then** it is distinguishable from user functional
   data where necessary and follows Privacy (021) for any user-linked data.

### User Story 11 - Observability degraded mode & extensibility (Priority: P1)

The observability system is itself non-blocking: if observability is unavailable, the portal keeps working,
critical features do not depend on its dashboard, observation data may be temporarily unavailable, and no
functional data is destroyed. Plugins/connectors declare observable info through a common model rather than
each building its own monitoring.

**Why this priority**: Two explicit requirements: observability must never become a blocking dependency,
and extensibility must be uniform (no per-plugin monitoring silos).

**Independent Test**: Make observability itself unavailable; confirm the portal and critical features keep
working and no functional data is lost; add a plugin/connector that declares observable metrics/states/
checks/errors/events/tasks/syncs and confirm they integrate via the common model.

**Acceptance Scenarios**:

1. **Given** observability is unavailable, **When** the portal runs, **Then** it continues to function,
   critical features do not depend on the observability dashboard, observation data may be temporarily
   unavailable, and functional data is not destroyed.
2. **Given** a plugin/connector, **When** it declares observable info (metrics/states/checks/errors/events/
   tasks/syncs), **Then** it integrates via the common observable-contribution model (not its own
   monitoring system), per Extensibility (023).
3. **Given** a failing observability component, **When** it fails, **Then** unrelated portal functions
   remain usable (isolation).

### Edge Cases

- **Technically up, functionally broken**: surfaced as functionally degraded even if "green" technically.
- **Service available but sync broken**: distinguishable; a failed sync never deletes already-synced data
  (005).
- **Anomaly ≠ incident**: an anomaly is not auto-promoted; escalation to an Incident follows the defined
  rule and uses Support (016).
- **Two incident systems**: forbidden — Observability feeds the existing Incident system only.
- **Secret in a log/trace**: must never happen; secrets are redacted/excluded by design.
- **Private AI/user content in dashboards**: never auto-exposed; metadata-only.
- **Observability down**: portal keeps working; critical paths independent of the observability dashboard.
- **Plugin builds its own monitoring**: discouraged — must use the common observable model.
- **Standard user reaching internals**: denied by default (003).
- **Performance threshold hard-coded**: avoided here; thresholds are configurable/architecture-dependent.
- **Observability history vs user data retention**: separable; user-linked observability data follows
  Privacy (021) and deletion/anonymization.
- **Duplicate/late observability events**: idempotent per 007.

## Requirements *(mandatory)*

### Functional Requirements

#### Portal Observability (self-observation)
- **FR-001**: The portal MUST be able to observe itself and expose, per permissions, global portal state,
  availability, errors, performance, events, synchronizations, automations, plugins, connectors, AI,
  long-running tasks, background processing, queues (where relevant), incidents, and anomalies.
- **FR-002**: Observability MUST NOT be limited to CPU/RAM metrics; it MUST cover functional operation of
  the portal's components.

#### Technical vs Functional Health (explicit distinction)
- **FR-003**: The system MUST represent **technical health** (availability, response time, errors, failure
  rate, latency, in-progress/failed/interrupted processing, resource consumption where available) without
  imposing a particular monitoring technology.
- **FR-004**: The system MUST represent **functional health** (e.g., syncs no longer completing, events no
  longer processed, automations failing, notifications no longer sent, degraded connectors, blocked tasks,
  abnormally stale data, abnormal error rate) and MUST surface functional degradation even when technical
  health is green.
- **FR-005**: Technical and functional health MUST be modeled and displayed as **distinct** axes and MUST
  NOT be conflated.

#### Events / Synchronization / Automation Observability
- **FR-006**: The event system (007) MUST be observable per permissions: received/processed/failed/ignored/
  duplicated/pending events, processing time, origin, and reactions where relevant; diagnostic info MUST be
  retained without exposing private payload data unless permissions/privacy allow.
- **FR-007**: Synchronizations (005/006) MUST be observable: last/next sync, duration, counts (added/
  modified/removed-or-disabled/ignored/errored), last error, current state, and data freshness; the view
  MUST make "service available ≠ sync functional" obvious, and MUST reflect that a failed sync did not
  delete already-synced data.
- **FR-008**: The automation engine (019) MUST be observable: active rules, executions, success/failure,
  durations, unmet conditions, actions performed/failed, detected loops, suspended rules + suspension
  reasons; an auto-suspended (loop/repeat) automation MUST be clearly identifiable.

#### Plugin & Connector Observability
- **FR-009**: Each plugin MUST expose an observability state via a common model: active/disabled/error/
  incompatible/invalid-config/missing-dependency, version, last activity, recent errors; a failing plugin
  MUST NOT make the whole portal unavailable (isolation per 023).
- **FR-010**: Each connector MUST be observable (completing Services & Health 006, not replacing it): state,
  last connection/sync, errors, latency, available data/capabilities, last activity — distinguishing
  connector-functional vs external-service-unavailable vs invalid-auth vs sync-error vs stale.

#### AI Observability
- **FR-011**: The AI capability (018) MUST be observable: requests, response time, errors, timeouts,
  provider availability, model used, consumption (where available), tools/connectors used, actions
  performed, failure rate.
- **FR-012**: AI observability MUST NOT automatically expose the private content of conversations in stats/
  dashboards; only technical metadata MUST be retained where needed.

#### Performance Observability
- **FR-013**: The system MUST identify performance problems (slow pages/widgets/connectors/searches/AI/
  syncs/automations) and MUST attribute time to portal-wait vs external-service-wait vs
  internal-processing vs timeout.
- **FR-014**: This spec MUST NOT impose fixed technical performance thresholds; thresholds MUST be
  configurable/architecture-dependent.

#### Structured Errors
- **FR-015**: Observed errors MUST be structured, carrying (as applicable): timestamp, component, service,
  plugin, event, concerned user (if relevant and permitted), category, level, message, necessary technical
  context, frequency, first occurrence, last occurrence, state, and resolution.
- **FR-016**: Errors MUST be diagnosable (no generic un-diagnosable errors) and MUST NOT contain secrets.

#### Anomaly Detection & Incident Escalation
- **FR-017**: The system MUST be able to detect anomalies (error spike, abnormally long sync, repeated
  automation, blocked event, unstable service, latency spike, repeated failure); an anomaly MUST NOT be
  automatically an incident.
- **FR-018**: The system MUST implement the escalation **Observation → Anomaly → Incident** only when the
  defined trigger conditions are met, with automatic or human validation per rule.
- **FR-019**: Escalation MUST feed the **existing Incident system (016)** (create → notify → track →
  resolve); Observability MUST NOT create a second, independent incident system.

#### Alerting & Diagnostic Actions
- **FR-020**: Observability MUST produce alerts (e.g., portal degraded, critical sync failure, suspended
  automation, connector unavailable, critical storage, repeated error, AI unavailable) through the existing
  Notifications engine (010) — no separate notification mechanism.
- **FR-021**: Observability MUST offer contextual diagnostic actions where relevant (rerun sync/task, test
  connector, disable a problematic automation, open docs, open/create an incident, view history, ask the
  AI); sensitive actions MUST be permission-gated (003) and audited.
- **FR-022**: Observability events MUST be usable as triggers by the existing Automations (019) and
  Notifications (010) rules (observability is a trigger source, not a new engine).

#### Admin Dashboard (action-first)
- **FR-023**: Observability MUST provide an admin dashboard showing global health, active problems,
  incidents, degraded services, errored syncs, errored automations, problematic plugins, recent errors,
  performance, AI, and infrastructure (where available).
- **FR-024**: The dashboard MUST prioritize (1) problems needing action, (2) impact, (3) criticality, (4)
  age, (5) details — and MUST NOT become a flat collection of hundreds of metrics.
- **FR-025**: The observability dashboard SHOULD integrate with / feed the Administration Control Center
  (020) rather than duplicate it; each panel MUST degrade gracefully.

#### History, Trends & Retention
- **FR-026**: Observability MUST retain history and trends (errors, availability, incidents, syncs,
  performance, automations, plugins, AI) over adapted periods.
- **FR-027**: Observability retention MUST be configurable where relevant; voluminous/detailed technical
  data MAY have shorter retention than important business events; data MUST NOT be kept indefinitely
  without reason.
- **FR-028**: Observability history MUST be distinguishable from user functional data where necessary;
  user-linked observability data MUST follow Privacy (021) retention/deletion/anonymization.

#### Permissions & Privacy
- **FR-029**: Observability MUST be primarily administrative/privileged and gated by the authorization
  engine (003, deny-by-default); standard users MUST NOT by default access technical logs, sensitive
  infrastructure info, detailed internal errors, other users' data, or anything revealing secrets.
- **FR-030**: Support and Admin MAY have different observability levels per the Permission Model; user data
  MUST be exposed only when necessary, permitted, and justified (021) — observability MUST NOT be a privacy
  bypass.
- **FR-031**: Logs/traces/errors MUST exclude secrets (tokens, passwords, API keys, OIDC secrets) and
  unnecessary sensitive data.

#### Degraded Mode (observability is non-blocking)
- **FR-032**: Observability MUST NOT be a blocking dependency of the portal: if observability is
  unavailable, the portal MUST keep functioning, critical features MUST NOT depend on its dashboard,
  observation data MAY be temporarily unavailable, and functional data MUST NOT be destroyed.
- **FR-033**: A failing observability component MUST be isolated so unrelated portal functions remain
  usable.

#### Extensibility, Search, Events/History integration
- **FR-034**: Plugins and connectors MUST be able to declare observable info (metrics, states, checks,
  errors, events, tasks, syncs) through a **common observable-contribution model** (not each its own
  monitoring), per Extensibility (023).
- **FR-035**: Relevant observable items (incident, service, automation, plugin, error, synchronization) MAY
  be indexed in global Search (008) per permissions, with sensitive data protected.
- **FR-036**: Important observability events MUST be historized via Events & History (007) per retention
  policy, distinguishing current state vs technical event vs incident vs history vs aggregated metric;
  consumers MUST be idempotent per 007.
- **FR-037**: The AI (018) MUST be able to use observability information accessible to the user, presenting
  observed facts, historical data, hypotheses, and recommendations **distinctly** (never a hypothesis as a
  fact), bounded by the user's permissions.

### Observation → Anomaly → Incident Model (normative)

- **Observation**: a recorded observable fact/measure (health check, count, latency, error, state).
- **Anomaly**: a detected abnormal pattern derived from observations (spike, stall, repeated failure); it
  is a signal, **not** an incident.
- **Incident**: created only when an anomaly meets the defined escalation rule, **in the Support/Incident
  system (016)** — with automatic or human validation per rule — then notified/tracked/resolved there.

**Invariants**:
- Anomaly is never auto-promoted without meeting the rule.
- No second incident system; Observability feeds Support (016).
- Alerts via Notifications (010); triggers/actions via Automations (019); no parallel engines.

### Health Model (two axes)

- **Technical Health**: available / responding / latency / error-rate / resource usage (where available).
- **Functional Health**: is the component actually performing its function (sync completing, events
  processed, notifications sent, data fresh, error rate normal)?
- A component is **healthy** only when both axes are healthy; "technically up, functionally degraded" is a
  first-class, distinct state.

### Observability-Related Domain Events (produced; consumed via 007/019/010)

- `observability.health_changed` (component technical/functional health transition)
- `observability.error_recorded` (structured error)
- `observability.anomaly_detected`
- `observability.alert_raised`
- `observability.diagnostic_action_performed` (sensitive; audited)
- `sync.*`, `automation.*`, `plugin.*`, `service.status_changed`, `incident.*` (referenced; owned by their
  specs — Observability observes, it does not redefine them)

### Key Entities

- **Observation / Health Signal**: a recorded measure/state for a component (technical and/or functional).
- **Component Health**: the two-axis health (technical + functional) of a portal component (events, sync,
  automations, plugins, connectors, AI, tasks, portal-global).
- **Structured Error**: a diagnosable error record (fields per FR-015), secret-free.
- **Anomaly**: a detected abnormal pattern; candidate for escalation.
- **Observability Alert**: an alert produced via Notifications (010).
- **Diagnostic Action**: a contextual admin action (rerun/test/disable/open-incident/view-history/ask-AI),
  permissioned + audited.
- **Observability History / Trend**: time-series of observability data with its own retention.
- **Observable Contribution (plugin/connector)**: declared metrics/states/checks/errors/events/tasks/syncs
  via the common model.
- **Incident (referenced, owned by 016)** / **Service State/Sync State (referenced, owned by 005/006)** /
  **Permission/Visibility (referenced, 003/021)**.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The admin can determine portal/component/sync/event/automation/plugin/connector/AI health and
  "where/since-when/impact/actions" from the observability dashboard in 100% of defined cases, with
  problems ordered action-first (not a flat metric wall).
- **SC-002**: Technical health and functional health are presented as distinct axes in 100% of cases; a
  "technically up, functionally degraded" component is reported as degraded in 100% of such cases.
- **SC-003**: Events/sync/automation observability reflects correct counts/states in 100% of defined cases;
  "service available ≠ sync functional" is distinguishable in 100% of cases; a failed sync shows data was
  not deleted in 100% of cases.
- **SC-004**: A failing plugin/connector makes the whole portal unavailable in 0% of cases; its failure is
  observable in 100% of cases.
- **SC-005**: AI private conversation content appears in observability stats/dashboards in 0% of cases;
  AI technical metadata is observable in 100% of defined cases.
- **SC-006**: Performance delays are attributed to portal-wait/external/internal/timeout in 100% of defined
  cases; this spec hard-codes a performance threshold in 0% of cases.
- **SC-007**: Observed errors are structured and diagnosable in 100% of cases; a secret appears in a log/
  trace/error in 0% of cases.
- **SC-008**: An anomaly is auto-promoted to an incident without meeting the escalation rule in 0% of
  cases; a second independent incident system exists in 0% of cases (escalation uses Support 016 in 100%).
- **SC-009**: Observability alerts are delivered via the Notifications engine in 100% of cases; a separate
  notification mechanism is used in 0% of cases.
- **SC-010**: Standard users access observability internals (logs/infra/internal errors/others' data/
  secrets) in 0% of cases; sensitive diagnostic actions are audited in 100% of cases.
- **SC-011**: When observability is unavailable, the portal keeps functioning and functional data is
  destroyed in 0% of cases; a failing observability component breaks unrelated functions in 0% of cases.
- **SC-012**: Plugins/connectors declaring observable info use the common model in 100% of cases (no
  per-plugin monitoring silo); each major capability has verifiable acceptance criteria (this spec).

## Assumptions

- Services & Health (006) remains the owner of service state/availability/incident-surfacing on service
  surfaces; Observability **completes** it with portal-wide self-observation and never replaces it.
- The Incident lifecycle is owned by Support (016); alerting by Notifications (010); triggers/actions by
  Automations (019); the event/history backbone and dedup by Events & History (007); authorization by
  Roles & Permissions (003); visibility/retention/deletion by Privacy (021); the admin Control Center by
  Administration (020); plugin/connector contribution by Extensibility (023). Observability composes with
  all of these.
- Performance thresholds, anomaly-detection thresholds, and retention durations are configurable/
  architecture-dependent and are NOT fixed here. (Flagged as OQ-120/OQ-121/OQ-122.)
- "Infrastructure where available" reuses the infrastructure metrics defined by Services & Health (006);
  Observability does not redefine CPU/RAM/GPU/etc.

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation. (Genuinely Observability-specific; cross-cutting ones already tracked
elsewhere are referenced, not re-opened.)

- **OQ-120 (Anomaly-detection model)**: Confirm how anomalies are detected (baseline/threshold/trend/
  rule-based) and the configurable parameters, without choosing technology.
- **OQ-121 (Escalation rules)**: Confirm the precise Observation→Anomaly→Incident escalation rules
  (auto vs human validation, thresholds, dedup of repeated anomalies into one incident).
- **OQ-122 (Observability retention)**: Confirm default retention per data type (detailed technical vs
  aggregated vs important events) and configurability; aligns with Events OQ-33 / Privacy OQ-101.
- **OQ-123 (Support vs Admin observability levels)**: Confirm exactly which observability views/actions
  Support may access vs Admin-only, aligning with Permissions OQ-76 (support permission split).
- **OQ-124 (Observability storage vs event backbone)**: Confirm whether high-volume observability data is
  stored distinctly from the business event/history store (for retention/performance) while important
  observability events still flow through 007 — a functional/retention decision, not a tech choice.

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference) and the project
  Constitution (v1.0.0) — especially principle XIII (Observability & Auditability).
- Composes with (does not re-implement/replace): `003-roles-permissions` (privileged access; audit),
  `005-connectors` (connector/sync observability; failed-sync-not-deleting), `006-services-health`
  (service state/health/infra — **completed, not replaced**), `007-events-history` (observability events/
  history; idempotency; dedup), `008-search-command-palette` (indexing observable items),
  `009-dashboard-widgets` (observability widgets), `010-notifications` (alerting), `016-support`
  (Incident escalation — single incident system), `018-ai-capability` (AI observability + AI using
  observability data within permissions), `019-automations` (observability triggers/actions; suspended-rule
  visibility), `020-administration` (admin Control Center integration), `021-privacy-data-lifecycle`
  (permissions/privacy/retention; secrets exclusion), `023-extensibility` (common observable-contribution
  model).
- Depends on / references: `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`,
  `product/GLOSSARY.md`, `architecture/FUNCTIONAL_ARCHITECTURE.md`, `architecture/EVENT_MODEL.md`,
  `architecture/DATA_MODEL.md`, `architecture/PERMISSION_MODEL.md`, `features/FEATURE_CATALOG.md`
  (CORE-023 Observability, CORE-018 Degraded Mode, ADMIN-013 Portal health).
- Contradictions check: none found with specs 001–024; this spec closes audit gap **H2** (Observability
  unspecified) and the "future Observability spec" forward references in Administration (020) and Services
  & Health (006).
