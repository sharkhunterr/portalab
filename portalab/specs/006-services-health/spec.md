# Feature Specification: Services & Health

**Feature Branch**: `006-services-health`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Detailed functional specification of the Services & Health system."

## Role of This Document

This is a **detailed feature specification** for Services & Health — the module and surfaces that
let users see the state, availability, health history, and (for privileged users) detailed
infrastructure of connected services, including the service detail page. It conforms to and refines
the superior reference specification (`specs/001-portal-global-spec/spec.md`) and composes with Roles
& Permissions (`specs/003-roles-permissions/spec.md`), the Portal Core shell
(`specs/004-portal-core-shell/spec.md`), and Connectors (`specs/005-connectors/spec.md`), under the
project Constitution (`.specify/memory/constitution.md`, v1.0.0). It draws on
`architecture/FUNCTIONAL_ARCHITECTURE.md`, `architecture/EVENT_MODEL.md`, `architecture/DATA_MODEL.md`,
`product/BUSINESS_RULES.md`, `ux/UX_PRINCIPLES.md`, and `ux/DESIGN_SYSTEM.md`.

Scope boundary: this spec owns the **presentation and interpretation of service health** — service
state, availability/uptime, last check, last errors, monitoring display, infrastructure metrics,
privileged server operations, permission-based visibility, health history, and the service detail
page. It **consumes** connector mechanics, sync, and capability data from the Connectors spec; it
does **not** own connector configuration/sync internals, the authorization engine, the full Incident
and Maintenance lifecycles, or the Support/Ticket system — it references and composes with them. It
chooses no technology and contains no implementation detail.

**Terminology** (aligned with the global spec and Glossary): Service = a concrete connected instance;
Capability = a functional ability; Domain Event = a recorded fact; `occurred_at` = real occurrence
time; `received_at` = portal receipt time.

### Strict Conceptual Distinctions (normative)

These five concepts are **distinct** and MUST never be conflated in data, UI, or logic:

- **Service State**: the live operational condition of a service instance right now
  (Operational, Degraded, Unavailable, Maintenance, Unknown). It is derived from monitoring.
- **Incident**: a recorded broad/systemic problem narrative with its own lifecycle
  (created/updated/resolved), owned by Support/Incidents; a service may be Degraded or Unavailable
  with or without an open Incident.
- **Maintenance**: a scheduled or ongoing planned operation window; while active it explains a
  Maintenance state but is a separate planned record, not a failure.
- **Ticket**: an individual user-reported issue; it is never the same as a Service State or an
  Incident, though a Ticket may reference either.
- **Sync State**: the state of data synchronization for the service (last run outcome, syncing),
  owned by Connectors; it is independent of Service State (a service can be Operational yet have a
  failed last sync, or Unavailable yet have valid historized data).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See service state at a glance (Priority: P1)

Any permitted user sees, for each service they may view, a clear current Service State (Operational,
Degraded, Unavailable, Maintenance, Unknown) with availability and last-check information, so they
understand what is working right now.

**Why this priority**: The core value of Services & Health is answering "is it working?" instantly;
every other detail builds on a trustworthy, distinguishable state.

**Independent Test**: As a standard permitted user, view the services overview and a service's state;
confirm each of the five states renders distinguishably with availability and a last-check timestamp,
and that an unknown/unreachable monitor shows Unknown rather than a false Operational.

**Acceptance Scenarios**:

1. **Given** a monitored service, **When** its state is viewed, **Then** it shows one of Operational,
   Degraded, Unavailable, Maintenance, or Unknown, with a last-check time.
2. **Given** monitoring cannot determine state, **When** the state is viewed, **Then** it shows
   Unknown (never a misleading Operational).
3. **Given** a scheduled maintenance window is active, **When** the state is viewed, **Then** it shows
   Maintenance (not Unavailable), referencing the planned maintenance record.

### User Story 2 - Permission-appropriate visibility: standard vs privileged (Priority: P1)

A standard user sees high-level, permission-appropriate information (state, availability, maybe
uptime), while a privileged user with infrastructure permission additionally sees detailed metrics
(CPU, RAM, storage, GPU, network, temperature, transcoding) and privileged operations.

**Why this priority**: "A standard user sees info adapted to permissions; a privileged user accesses
detailed infrastructure" is the explicit requirement and a security/privacy boundary.

**Independent Test**: View the same service as a standard user and as a user with
`infrastructure.read`/`services.manage`; confirm the standard user sees only high-level state while
the privileged user additionally sees detailed metrics and operations, enforced server-side.

**Acceptance Scenarios**:

1. **Given** a standard user without infrastructure permission, **When** they view a service, **Then**
   they see state/availability/uptime but NOT detailed infrastructure metrics or privileged
   operations.
2. **Given** a user with `infrastructure.read`, **When** they view a service, **Then** they
   additionally see CPU, RAM, storage, GPU, network, temperature, and transcoding/load where the
   service exposes them.
3. **Given** a user with `services.manage`, **When** privileged operations are available, **Then** the
   operations are offered and each sensitive action is confirmed and audited; absent the permission,
   the operations are not offered and are refused server-side if attempted.
4. **Given** any visibility difference, **When** evaluated, **Then** it is enforced server-side, not
   merely hidden in the UI.

### User Story 3 - Service detail page (Priority: P1)

A permitted user opens a service's detail page and sees a coherent picture: current state,
availability/uptime, last check, recent errors, relevant monitoring, any active/planned maintenance
and linked incidents, sync state, health history, and — for privileged users — infrastructure metrics
and operations.

**Why this priority**: The service detail page is the primary surface where the five distinct
concepts come together while remaining clearly separated; it is explicitly required.

**Independent Test**: Open a service detail page; confirm it presents state, availability/uptime, last
check, last errors, health history, sync state, and (for privileged users) infrastructure/operations,
with Service State, Incident, Maintenance, Ticket, and Sync State visibly distinct.

**Acceptance Scenarios**:

1. **Given** a permitted user, **When** they open a service detail page, **Then** it shows current
   Service State, availability, uptime, last check, and recent errors.
2. **Given** the detail page, **When** it shows an active Maintenance, a linked Incident, a related
   Ticket, and the Sync State, **Then** each is presented as a distinct element, not merged into the
   state.
3. **Given** the detail page, **When** a privileged user views it, **Then** infrastructure metrics and
   available operations appear in addition to the standard information.
4. **Given** the detail page, **When** any section's source is slow/unavailable, **Then** that section
   shows its own functional state without blocking the rest of the page.

### User Story 4 - Health history (Priority: P2)

Users with the right permission can view a service's health history — how its state and availability
evolved over time, including past errors — distinct from incident narratives and from sync history.

**Why this priority**: Health history turns momentary state into understandable reliability over time
and supports diagnosis; it must not be confused with incidents or sync history.

**Independent Test**: View a service's health history and confirm it shows state/availability changes
and past errors over time, is permission-gated, and is distinct from the Incident list and the Sync
history.

**Acceptance Scenarios**:

1. **Given** a permitted user, **When** they view health history, **Then** it shows the evolution of
   Service State and availability (and past errors) over a time range.
2. **Given** health history, **When** compared with incidents and sync history, **Then** the three are
   separate records and are not merged.
3. **Given** health history entries, **When** recorded, **Then** they use `occurred_at` for when the
   condition actually occurred, distinct from `received_at`.

### User Story 5 - Monitoring, availability, uptime, last check, last errors (Priority: P2)

The system monitors services and derives availability, uptime, last-check time, and recent errors,
presenting them with correct freshness/staleness indications.

**Why this priority**: These are the raw signals that make state trustworthy; stale or ambiguous
signals would mislead users.

**Independent Test**: Observe a monitored service and confirm availability, uptime, last-check time,
and recent errors are shown and that stale data is marked stale rather than presented as current.

**Acceptance Scenarios**:

1. **Given** a monitored service, **When** monitoring runs, **Then** availability, uptime, last-check
   time, and recent errors are updated and shown.
2. **Given** monitoring data has not refreshed recently, **When** displayed, **Then** it is marked
   stale (and may fall to Unknown) rather than presented as current.
3. **Given** recent errors exist, **When** shown, **Then** they are actionable and do not expose
   secrets.

### User Story 6 - Infrastructure monitoring and privileged server operations (Priority: P2)

Where a service/host exposes them, privileged users can view infrastructure metrics (CPU, RAM,
storage, GPU, network, temperature, transcoding/load) and perform server operations (e.g.,
Unraid-style operations) when available, each operation being permission-gated, confirmed, and
audited.

**Why this priority**: Infrastructure visibility and operations are high-value but high-risk; they
must be strictly permissioned and auditable.

**Independent Test**: As a privileged user, view infrastructure metrics where exposed and perform an
available server operation; confirm it is confirmed and audited; as a standard user, confirm neither
is available.

**Acceptance Scenarios**:

1. **Given** a service/host that exposes infrastructure metrics, **When** a privileged user views it,
   **Then** CPU, RAM, storage, GPU, network, temperature, and transcoding/load are shown where
   available, each with its own functional state.
2. **Given** server operations are available (e.g., Unraid-style), **When** a user with the operation
   permission performs one, **Then** it is treated as sensitive, confirmed where appropriate, and
   audited.
3. **Given** a service does not expose a given metric or operation, **When** viewed, **Then** that
   item shows a clear "not available" rather than a fabricated value.

### User Story 7 - Degraded mode and partial failure isolation (Priority: P1)

When monitoring, infrastructure sources, or a specific service are slow or unavailable, the Services &
Health surfaces remain usable: each affected element shows its own state while unrelated services and
sections continue to work.

**Why this priority**: Graceful degradation and "slow components never block unrelated content" are
locked principles; health surfaces are themselves prone to partial failure.

**Independent Test**: Simulate an unreachable service, a stale metric source, and a slow health-history
load; confirm each shows its own state and the rest of the Services overview/detail remains usable.

**Acceptance Scenarios**:

1. **Given** one unreachable service, **When** the services overview is viewed, **Then** that service
   shows Unavailable/Unknown while other services display normally.
2. **Given** a slow infrastructure source, **When** the detail page loads, **Then** the metrics section
   shows loading/stale while state, uptime, and history remain usable.
3. **Given** broad degradation, **When** the module loads, **Then** core service state information
   remains available even if detailed metrics do not.

### Edge Cases

- **Operational service with failed last sync**: Service State shows Operational while Sync State
  shows the failed last run; the two are displayed separately and never merged.
- **Unavailable service with valid historized data**: State shows Unavailable while previously
  historized data/metrics are shown as stale/historical, not live.
- **Maintenance vs Unavailable**: An active maintenance window yields Maintenance, not Unavailable;
  when the window ends, state returns to its monitored value.
- **Incident open but service recovered**: Service State may be Operational while an Incident remains
  open until explicitly resolved; the two lifecycles are independent.
- **Monitoring source down**: State falls to Unknown (not Operational); the detail page indicates
  monitoring itself is unavailable.
- **Metric partially available**: If a host exposes CPU but not GPU, GPU shows "not available" rather
  than zero or a fabricated value.
- **Permission downgrade mid-session**: A user who loses `infrastructure.read` stops seeing detailed
  metrics on next evaluation (server-side), even if previously visible.
- **Privileged operation on an unavailable host**: The operation is offered only when meaningful;
  attempting it against an unreachable host returns an actionable error, not a silent failure.
- **Stale uptime after reconnection**: Uptime/availability clearly reflect the monitored source and
  mark gaps rather than inventing continuity.
- **Ticket referencing a service**: A Ticket about a service is shown as a related Ticket, never as the
  service's state or as an Incident.
- **Health history vs sync history**: Both are time series but are distinct records with distinct
  meanings; they are never shown as one list.
- **Secrets in errors/metrics**: Error details and metrics never expose credentials or secrets.

## Requirements *(mandatory)*

### Functional Requirements

#### Service Instances & State
- **FR-001**: The system MUST represent each connected service as an instance with a current Service
  State that is exactly one of: Operational, Degraded, Unavailable, Maintenance, Unknown.
- **FR-002**: Service State MUST be derived from monitoring signals and MUST fall to Unknown when
  monitoring cannot determine it (never a misleading Operational).
- **FR-003**: An active Maintenance window MUST yield the Maintenance state (not Unavailable), and the
  state MUST return to its monitored value when the window ends.
- **FR-004**: Service State, Incident, Maintenance, Ticket, and Sync State MUST be modeled and
  displayed as distinct concepts and MUST NEVER be merged or conflated.

#### Availability, Uptime, Last Check, Last Errors
- **FR-005**: The system MUST compute and present availability, uptime, last-check time, and recent
  errors for each service, to permitted users.
- **FR-006**: Stale monitoring data MUST be marked stale (and MAY drive the state to Unknown) rather
  than presented as current.
- **FR-007**: Recent errors MUST be actionable and MUST NOT expose secrets or credentials.

#### Monitoring
- **FR-008**: The system MUST monitor services and update their state, availability, uptime,
  last-check time, and recent errors on an ongoing basis.
- **FR-009**: Monitoring failures MUST be isolated so a failure to monitor one service does not break
  monitoring or display of others.

#### Permission-Based Visibility
- **FR-010**: The system MUST present permission-appropriate information: standard users see
  state/availability/uptime; detailed infrastructure metrics require `infrastructure.read`; privileged
  operations require `services.manage`.
- **FR-011**: All visibility differences MUST be enforced server-side (deny-by-default), not merely
  hidden in the UI.
- **FR-012**: Health information MUST respect privacy and admin visibility policies where applicable;
  permission to read MUST NOT override privacy constraints.

#### Infrastructure Metrics
- **FR-013**: Where a service/host exposes them, the system MUST present CPU, RAM, storage, GPU,
  network, temperature, and transcoding/load to users with `infrastructure.read`.
- **FR-014**: A metric that a service does not expose MUST show a clear "not available" rather than a
  fabricated or zero value.
- **FR-015**: Each infrastructure metric section MUST have its own functional state (loading, stale,
  unavailable) and MUST NOT block unrelated sections.

#### Server Operations (e.g., Unraid-style)
- **FR-016**: Where a service/host exposes server operations, the system MUST offer them only to users
  with the appropriate operation permission and only when the operation is meaningful.
- **FR-017**: Every server operation MUST be treated as sensitive: confirmed where appropriate and
  audited with actor, action, timestamp, context, and result.
- **FR-018**: Attempting an operation against an unreachable/unavailable host MUST return an actionable
  error, not a silent failure.

#### Incidents & Maintenance (relations)
- **FR-019**: The system MUST be able to associate and display known Incidents and Maintenance windows
  relevant to a service, while keeping them distinct from Service State (lifecycles owned by Support).
- **FR-020**: A service MAY be Degraded/Unavailable with or without an open Incident, and an Incident
  MAY remain open after the service has recovered; the two lifecycles MUST be independent.
- **FR-021**: Known Incidents and active Maintenance MUST be surfaced on relevant service surfaces to
  aid understanding and reduce duplicate tickets.

#### Sync State (relation)
- **FR-022**: The system MUST display the service's Sync State (last run outcome, syncing) as distinct
  from Service State; a service MAY be Operational with a failed last sync, or Unavailable with valid
  historized data.

#### Health History
- **FR-023**: The system MUST maintain and present, to permitted users, a health history showing the
  evolution of Service State and availability over time, including past errors.
- **FR-024**: Health history MUST be distinct from the Incident list and from Sync history and MUST
  NOT be merged with them.
- **FR-025**: Health history entries MUST use `occurred_at` for actual occurrence time, distinct from
  `received_at`, and consumers MUST be idempotent where duplicate delivery is possible.

#### Service Detail Page
- **FR-026**: The service detail page MUST present current Service State, availability, uptime, last
  check, and recent errors to permitted users.
- **FR-027**: The service detail page MUST present active Maintenance, linked Incidents, related
  Tickets, and Sync State as visibly distinct elements.
- **FR-028**: The service detail page MUST present infrastructure metrics and available operations to
  privileged users in addition to the standard information.
- **FR-029**: Each section of the detail page MUST render its own functional state so a slow/unavailable
  source does not block the rest of the page.

#### Degraded Mode
- **FR-030**: Services & Health surfaces MUST remain usable under partial failure: unreachable or stale
  sources show their own state while unrelated services/sections continue to function.
- **FR-031**: Under broad degradation, core Service State information MUST remain available even when
  detailed metrics do not.

#### Events & Audit
- **FR-032**: Service State changes MUST emit domain events (`service.status_changed`, and
  maintenance/incident-related events where applicable) with `occurred_at` distinct from `received_at`.
- **FR-033**: Sensitive health-related actions (server operations, privileged metric access where
  configured sensitive) MUST be audited with actor, action, timestamp, context, decision, and result.

### Service State Model

**States**: Operational, Degraded, Unavailable, Maintenance, Unknown.

**Derivation / transitions**:

- Unknown is the default when monitoring has no conclusive signal (e.g., monitor unreachable, data
  stale beyond threshold).
- Operational when monitoring confirms the service is fully functional.
- Degraded when monitoring indicates partial function (errors/latency above thresholds but not down).
- Unavailable when monitoring confirms the service is down/unreachable (and not in Maintenance).
- Maintenance when an active maintenance window applies; it overrides Operational/Degraded/Unavailable
  presentation for its duration and reverts to the monitored value afterward.

**Invariants**:
- Exactly one Service State is current per service at any time.
- Service State is independent of Incident status, Ticket status, and Sync State.
- Maintenance (planned) is never shown as Unavailable (failure).
- Stale/unknown monitoring never renders as Operational.

### Service/Health-Related Domain Events

Names aligned with the Event Model; each carries actor/context, service reference, metadata, version.

- `service.status_changed` (Service State transition)
- `service.health_recorded` (health-history point)
- `maintenance.scheduled` / `maintenance.started` / `maintenance.ended` (referenced; owned by Support)
- `incident.created` / `incident.updated` / `incident.resolved` (referenced; owned by Support)
- `service.operation_performed` (sensitive server operation; audited)

### Key Entities

- **Service Instance**: A concrete connected service with current Service State, availability, uptime,
  last check, recent errors, and (where exposed) infrastructure metrics and operations.
- **Service State**: The current operational condition (Operational, Degraded, Unavailable,
  Maintenance, Unknown), derived from monitoring.
- **Availability / Uptime**: Measures of reachability over time, with staleness indication.
- **Health History Entry**: A time-stamped record of state/availability/errors (`occurred_at`),
  distinct from incidents and sync history.
- **Infrastructure Metric**: A measured host/service metric (CPU, RAM, storage, GPU, network,
  temperature, transcoding/load) with its own availability/freshness; privileged-visibility.
- **Server Operation**: A privileged action against a service/host (e.g., Unraid-style), sensitive and
  audited.
- **Incident (referenced)**: A systemic problem narrative with its own lifecycle (owned by Support).
- **Maintenance (referenced)**: A planned operation window (owned by Support/Calendar).
- **Ticket (referenced)**: An individual user issue (owned by Support).
- **Sync State (referenced)**: The connector's synchronization status (owned by Connectors).
- **Permission/Policy (referenced)**: Visibility gating (owned by Roles & Permissions / Privacy).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every monitored service shows exactly one of the five Service States with a last-check
  time in 100% of views; monitoring with no conclusive signal renders Operational in 0% of cases
  (it renders Unknown).
- **SC-002**: Service State, Incident, Maintenance, Ticket, and Sync State are presented as merged/
  conflated in 0% of surfaces.
- **SC-003**: A standard user without `infrastructure.read` sees detailed infrastructure metrics or
  privileged operations in 0% of cases; a user with it sees exposed metrics in 100% of cases.
- **SC-004**: 100% of visibility differences are enforced server-side (not UI-only), verified by
  direct access attempts.
- **SC-005**: 100% of server operations produce an audit entry with actor, action, timestamp, context,
  and result; operations are offered to unpermitted users in 0% of cases.
- **SC-006**: Stale monitoring data is presented as current in 0% of cases (marked stale or Unknown in
  100%).
- **SC-007**: An unreachable single service blocks display of other services in 0% of cases; under
  broad degradation core state remains available in 100% of cases.
- **SC-008**: An active maintenance window is shown as Unavailable (failure) in 0% of cases (shown as
  Maintenance in 100%).
- **SC-009**: Health history is merged with the incident list or sync history in 0% of cases; health
  entries use `occurred_at` in 100% of cases.
- **SC-010**: A metric a service does not expose is shown as a fabricated/zero value in 0% of cases
  (shown as "not available" in 100%).

## Assumptions

- Connector mechanics, sync execution, and capability provisioning are owned by the Connectors spec;
  this spec consumes the resulting signals (reachability, sync outcome, metric capabilities).
- The full Incident, Maintenance, and Ticket lifecycles are owned by the Support/Calendar specs; this
  spec references and displays them while keeping them distinct from Service State.
- The authorization engine and privacy/visibility engine are owned by their specs; this spec consumes
  their decisions for permission-based visibility.
- "Unraid-style operations" is an example of host/server operations exposed by some services; the
  concrete operation catalog depends on what each service/host exposes and on permissions. (Flagged
  as OQ-27.)
- Monitoring cadence, staleness thresholds, and the Degraded-vs-Unavailable thresholds are configurable
  administrative policy; this spec requires their existence, not fixed values. (Flagged as OQ-25.)
- Health-history retention duration is administrative policy consistent with the Privacy/retention
  rules.

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation.

- **OQ-25 (State thresholds & cadence)**: Confirm how Degraded vs Unavailable vs Unknown are
  determined (thresholds, probe cadence, staleness-to-Unknown timeout) and whether these are global or
  per-service policy.
- **OQ-26 (Standard-user uptime exposure)**: Confirm exactly which fields a standard user may see
  (state + availability always; is uptime and last-error visible to standard users or privileged
  only?).
- **OQ-27 (Server-operation catalog & authorization)**: Confirm the catalog of server operations
  (e.g., Unraid-style) in scope and the precise permission(s) each requires, plus which are destructive.
- **OQ-28 (Health-history granularity/retention)**: Confirm the granularity and retention window of
  health history and whether standard users may view any of it.
- **OQ-29 (Infrastructure-permission granularity)**: Confirm whether a single `infrastructure.read`
  governs all metrics or whether certain metrics (e.g., temperature, GPU) are separately gated
  (relates to OQ-15 from Roles & Permissions).

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference) and the project
  Constitution (v1.0.0).
- Composes with: `specs/003-roles-permissions/spec.md` (`services.read`, `infrastructure.read`,
  `services.manage`; server-side visibility), `specs/004-portal-core-shell/spec.md` (functional-state
  presentation, degraded mode, navigation), and `specs/005-connectors/spec.md` (service connection,
  Sync State, capability/metric provisioning).
- Depends on / references: `architecture/FUNCTIONAL_ARCHITECTURE.md`, `architecture/EVENT_MODEL.md`,
  `architecture/DATA_MODEL.md`, `product/BUSINESS_RULES.md`, `ux/UX_PRINCIPLES.md`,
  `ux/DESIGN_SYSTEM.md`.
- Related specs (not owned here): Support (Incidents, Maintenance, Tickets), Calendar (maintenance
  calendar), Statistics (cross-service statistics), and the Privacy spec (021) (visibility engine).
