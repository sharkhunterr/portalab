# Feature Specification: Connectors

**Feature Branch**: `005-connectors`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Detailed functional specification of the Connectors system."

## Role of This Document

This is a **detailed feature specification** for the Connectors system — the integration layer that
connects external services to the portal and exposes their abilities to modules as **capabilities**.
It conforms to and refines the superior reference specification (`specs/001-portal-global-spec/spec.md`)
and composes with Roles & Permissions (`specs/003-roles-permissions/spec.md`) and the Portal Core
shell (`specs/004-portal-core-shell/spec.md`), under the project Constitution
(`.specify/memory/constitution.md`, v1.0.0). It draws on `architecture/FUNCTIONAL_ARCHITECTURE.md`,
`architecture/EXTENSIBILITY.md`, `architecture/EVENT_MODEL.md`, `architecture/DATA_MODEL.md`, and
`product/BUSINESS_RULES.md`.

Scope boundary: this spec owns the **connector lifecycle** (discovery, configuration, enable/disable,
connection test, connector state, compatibility, disconnection), the **capability contract** that
decouples modules from concrete services, and **synchronization** (runs, history, errors, resync) as
it pertains to connectors. It does **not** own module-internal presentation (e.g., the Services
module's detail UI, owned by its own spec), the authorization engine itself, nor the global
history/event store — it produces into and consumes from them. It chooses no technology and contains
no implementation detail.

**Terminology** (aligned with the global spec and Glossary): Connector = external integration;
Service = a concrete connected instance; Capability = a functional ability exposed to modules;
Domain Event = a recorded fact; `occurred_at` = real occurrence time; `received_at` = portal receipt
time.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Add a service via a connector without changing modules (Priority: P1)

An administrator connects a new external service through a connector. The connector declares which
capabilities the service provides; modules that consume those capabilities begin working with the new
service automatically, with no modification to the modules.

**Why this priority**: Capability-based integration — "a new service can be added without
fundamentally modifying existing modules" — is the product's core differentiator and the reason
Connectors exist.

**Independent Test**: Register a new service that provides a capability already consumed by a module;
confirm the module uses the new service through the capability without any module change, and that
the module never references the service by name.

**Acceptance Scenarios**:

1. **Given** a connector that declares a capability, **When** a service instance is connected and
   enabled, **Then** modules consuming that capability can use the service without module changes.
2. **Given** two different services providing the same capability, **When** either is connected,
   **Then** the consuming module functions with either, selecting via capability, not service name.
3. **Given** a newly connected service, **When** it is enabled, **Then** a `service.connected` event
   is recorded and its capabilities become available to permitted consumers.

### User Story 2 - Auto-discovery and manual configuration (Priority: P2)

An administrator can let the portal auto-detect candidate services where possible, or configure a
service manually; both paths lead to a configured connector ready for a connection test.

**Why this priority**: Both discovery and manual configuration are explicitly required; discovery
speeds setup while manual configuration guarantees coverage when detection is not possible.

**Independent Test**: Trigger auto-discovery and confirm detected candidates are presented for
confirmation; separately, configure a service manually with required settings; confirm both result in
a configured connector awaiting a connection test.

**Acceptance Scenarios**:

1. **Given** the environment supports detection, **When** auto-discovery runs, **Then** candidate
   services are presented for the administrator to confirm, never auto-enabled without confirmation.
2. **Given** a service that cannot be auto-detected, **When** the administrator configures it
   manually, **Then** it reaches a configured state equivalent to a discovered one.
3. **Given** a discovered candidate, **When** the administrator declines it, **Then** it is not
   connected and may be re-offered later.

### User Story 3 - Test connection before and after enabling (Priority: P1)

Before relying on a connector, the administrator runs a connection test that verifies reachability,
credentials, and compatibility, and reports a clear pass/fail with actionable diagnostics.

**Why this priority**: A connection test prevents enabling a misconfigured or incompatible connector
and underpins trustworthy service health and sync.

**Independent Test**: Run a connection test against a correctly configured service (expect pass) and a
misconfigured one (expect actionable failure); confirm the result does not enable/disable the
connector by itself.

**Acceptance Scenarios**:

1. **Given** a configured connector, **When** a connection test is run, **Then** it reports a clear
   pass or an actionable failure (reachability, credentials, or compatibility).
2. **Given** a failing connection test, **When** the result is shown, **Then** it explains the cause
   and suggested remediation rather than masking the failure.
3. **Given** a connection test, **When** it completes, **Then** it does not by itself change the
   enable/disable state of the connector.

### User Story 4 - Enable, disable, and connector state (Priority: P1)

A connector moves through clear states (configured, enabled, disabled, error, etc.); enabling makes its
capabilities available, disabling withdraws live access without deleting data, and the current state is
always distinguishable.

**Why this priority**: Clear connector state and safe enable/disable are prerequisites for graceful
degradation and for not losing data when a connector is turned off.

**Independent Test**: Enable a connector and confirm capabilities become available; disable it and
confirm live access/sync stops while historized data persists; confirm the connector's state is
distinguishable at each step.

**Acceptance Scenarios**:

1. **Given** a tested connector, **When** it is enabled, **Then** its capabilities become available to
   permitted consumers and a `service.status_changed` event is recorded.
2. **Given** an enabled connector, **When** it is disabled, **Then** live access and scheduled sync
   stop, its capabilities are withdrawn, and previously historized data is retained.
3. **Given** any connector, **When** its state is viewed, **Then** the state (configured, enabled,
   disabled, error, unavailable, maintenance, syncing) is distinguishable.

### User Story 5 - Synchronization, errors, and history (Priority: P1)

A connector synchronizes data from its service into the representations the portal needs; sync runs are
historized with start/finish/outcome, errors are captured without breaking unrelated functions, and
sync state is distinct from service health.

**Why this priority**: Synchronization is the mechanism by which external data appears in the portal;
its idempotency, error isolation, and history are locked requirements.

**Independent Test**: Run a sync and confirm a history entry with outcome; force a sync error and
confirm it is recorded, surfaced as a distinguishable state, and does not break unrelated functions;
confirm sync state is reported separately from service health.

**Acceptance Scenarios**:

1. **Given** an enabled connector, **When** a sync runs, **Then** `sync.started` and
   `sync.completed`/`sync.failed` events and a synchronization history entry (start, finish, outcome,
   counts) are recorded.
2. **Given** duplicate or late delivery, **When** sync processes events, **Then** the result is
   idempotent and `occurred_at` (not `received_at`) is used for attribution/ordering.
3. **Given** a sync failure, **When** it occurs, **Then** it is recorded with an actionable error,
   surfaced as a distinguishable state, and unrelated portal functions remain usable.
4. **Given** a connector, **When** its health and its sync state are viewed, **Then** they are
   reported as distinct facts.

### User Story 6 - Source of truth and conflict handling (Priority: P1)

The external service remains the source of truth for its native data; the portal stores only the
representations/history it needs; conflicting sources resolve by configured source-of-truth rules or
preserve provenance.

**Why this priority**: "External services remain sources of truth" and "conflicting sources follow
configured rules or preserve provenance" are locked business rules central to data integrity.

**Independent Test**: Change native data at the source and confirm the portal representation reconciles
to the source on sync; introduce a conflict and confirm it resolves by the configured rule or preserves
provenance rather than silently overwriting.

**Acceptance Scenarios**:

1. **Given** native data owned by a service, **When** it changes at the source, **Then** the portal's
   representation reconciles toward the source per source-of-truth rules.
2. **Given** conflicting values from different sources, **When** reconciled, **Then** the configured
   source-of-truth rule applies or provenance is preserved; nothing is silently overwritten.
3. **Given** portal-native data not owned by the service, **When** a sync runs, **Then** that data is
   not destroyed by the sync.

### User Story 7 - Resynchronization without destroying portal data (Priority: P2)

An administrator triggers a full or partial resynchronization to repair or refresh data; a full resync
reconciles with the source but must not blindly destroy native portal data or historized records.

**Why this priority**: "A full resync must not blindly destroy native portal data" is a locked rule;
resync is a powerful but dangerous operation needing explicit safeguards.

**Independent Test**: Trigger a full resync and confirm it reconciles representations with the source,
records a history entry, and leaves native portal data and prior history intact (not blindly deleted).

**Acceptance Scenarios**:

1. **Given** an enabled connector, **When** a full resync is triggered, **Then** it reconciles with the
   source, records a synchronization history entry, and does not blindly destroy native portal data.
2. **Given** a resync, **When** it runs, **Then** it is treated as a potentially sensitive operation,
   confirmed where appropriate, and audited.
3. **Given** a resync that would remove large amounts of data, **When** detected, **Then** it requires
   explicit confirmation rather than proceeding silently.

### User Story 8 - Disconnection and post-disconnection behavior (Priority: P1)

An administrator disconnects a service. Live access and sync stop and its capabilities are withdrawn,
but the portal's historized data is not automatically erased; the portal clearly reflects that the
data is historical/stale rather than live.

**Why this priority**: "Disconnecting a service removes live access/sync but does not necessarily
erase history" is a locked rule; mishandling it would destroy user data or mislead users.

**Independent Test**: Disconnect a service and confirm capabilities are withdrawn and sync stops, that
historized data remains available and is marked historical/stale, and that unrelated functions and
other connectors are unaffected.

**Acceptance Scenarios**:

1. **Given** a connected service, **When** it is disconnected, **Then** live access and sync stop, its
   capabilities are withdrawn, and a `service.disconnected` event is recorded.
2. **Given** a disconnected service, **When** its previously historized data is viewed, **Then** it
   remains available and is presented as historical/stale, not live.
3. **Given** a disconnection, **When** it completes, **Then** unrelated portal functions and other
   connectors remain unaffected, and no automatic erasure of portal history occurs.
4. **Given** an explicit, separately-authorized request to purge a disconnected service's data, **When**
   performed, **Then** it is a distinct sensitive, audited action — never an automatic side effect of
   disconnection.

### User Story 9 - Compatibility checking (Priority: P2)

Before enabling or updating a connector, the portal checks compatibility (portal version, required
capabilities, permissions, configuration) and refuses or warns when incompatible.

**Why this priority**: Compatibility checks prevent enabling connectors that would misbehave, aligning
with the Extensibility compatibility requirements.

**Independent Test**: Attempt to enable an incompatible connector and confirm it is refused with a clear
reason; enable a compatible one and confirm it proceeds.

**Acceptance Scenarios**:

1. **Given** a connector incompatible with the current portal version or missing dependencies, **When**
   enabling/updating is attempted, **Then** it is refused or warned with a clear reason.
2. **Given** a compatible connector, **When** enabling/updating is attempted, **Then** it proceeds.

### Edge Cases

- **Module depends on an absent capability**: A module requiring a capability that no connected
  service provides shows a distinguishable "unavailable/no data" state and does not break; it never
  hard-codes a service dependency.
- **Two services provide the same capability**: Resolution is deterministic (per configured
  selection/priority); the consuming module does not need to know which service served it.
- **Connector enabled but service unreachable**: The connector reports an error/unavailable state;
  sync is marked failed; historized data remains viewable as stale; unrelated functions continue.
- **Sync overlapping runs**: A new sync does not corrupt an in-flight one; runs are serialized or
  reconciled so history stays consistent and idempotent.
- **Credential expiry / auth failure during sync**: Captured as an actionable error; the connector
  surfaces the condition without erasing prior data.
- **Clock skew / late events**: `occurred_at` governs attribution/ordering, not `received_at`.
- **Disconnection during an active sync**: The in-flight sync terminates cleanly, is recorded as
  interrupted, and no partial write corrupts historized data.
- **Resync that would delete native/portal-owned data**: Guarded — requires explicit confirmation and
  never blindly destroys native portal data.
- **Auto-discovery false positives**: Candidates are never auto-enabled; they require explicit
  administrator confirmation.
- **Incompatible connector update**: Refused/warned via compatibility check; the previously working
  state is preserved.
- **Permission withdrawn for a consumer**: A consumer losing `services.read` no longer sees the
  capability data on next evaluation, independent of connector state.
- **Plugin-provided connector fails**: The failure is isolated; other connectors and unrelated portal
  functions remain usable.

## Requirements *(mandatory)*

### Functional Requirements

#### Capability Contract & Decoupling
- **FR-001**: A connector MUST declare the capabilities it provides, and modules MUST consume those
  capabilities without referencing any concrete service by name.
- **FR-002**: The system MUST allow multiple services to provide the same capability, with
  deterministic resolution (configured selection/priority) transparent to consuming modules.
- **FR-003**: Adding a new service that provides an already-consumed capability MUST require no change
  to existing modules.
- **FR-004**: When no connected service provides a required capability, consuming surfaces MUST show a
  distinguishable unavailable/no-data state rather than failing.

#### Discovery & Configuration
- **FR-005**: The system MUST support auto-discovery of candidate services where the environment
  permits, presenting candidates for explicit administrator confirmation (never auto-enabling).
- **FR-006**: The system MUST support manual configuration of a service, reaching a configured state
  equivalent to a discovered-and-confirmed one.
- **FR-007**: Connector configuration MUST validate required settings and MUST treat secrets as
  sensitive, never exposing them unnecessarily to clients.

#### Connection Test
- **FR-008**: The system MUST provide a connection test that verifies reachability, credentials, and
  compatibility and reports a clear pass or an actionable failure.
- **FR-009**: A connection test MUST NOT by itself change the connector's enable/disable state.

#### Enable / Disable & Connector State
- **FR-010**: The system MUST model an explicit connector state that is always distinguishable
  (at least: configured, enabled, disabled, syncing, error, unavailable, maintenance).
- **FR-011**: Enabling a connector MUST make its capabilities available to permitted consumers and
  MUST record a state-change event.
- **FR-012**: Disabling a connector MUST stop live access and scheduled sync and withdraw its
  capabilities, WITHOUT deleting its historized data.
- **FR-013**: Connector state changes MUST emit domain events (`service.status_changed`,
  `service.connected`, `service.disconnected`) with `occurred_at` distinct from `received_at`.

#### Synchronization, Errors & History
- **FR-014**: The system MUST synchronize service data into the representations the portal needs and
  MUST record each run in synchronization history (start, finish, outcome, counts, errors).
- **FR-015**: Synchronization MUST be idempotent where duplicate delivery is possible, using
  `occurred_at` for attribution/ordering.
- **FR-016**: Synchronization errors MUST be captured with actionable detail, surfaced as a
  distinguishable state, and MUST NOT break unrelated portal functions.
- **FR-017**: Sync state and service health MUST be represented as distinct facts.
- **FR-018**: The system MUST support manual synchronization in addition to any scheduled
  synchronization.

#### Source of Truth & Conflicts
- **FR-019**: External services MUST remain the source of truth for their native data; the portal MUST
  store only the representations/history its features require.
- **FR-020**: Conflicting sources MUST resolve via configured source-of-truth rules or MUST preserve
  provenance; the system MUST NOT silently overwrite conflicting data.
- **FR-021**: Portal-native data not owned by a service MUST NOT be destroyed by a routine sync.

#### Resynchronization
- **FR-022**: The system MUST support full and partial resynchronization that reconciles with the
  source and records a synchronization history entry.
- **FR-023**: A full resync MUST NOT blindly destroy native portal data or historized records.
- **FR-024**: A resync that would remove a large amount of data MUST require explicit confirmation and
  MUST be audited as a sensitive operation.

#### Disconnection & Post-Disconnection
- **FR-025**: Disconnecting a service MUST stop live access and sync, withdraw its capabilities, and
  record a `service.disconnected` event, WITHOUT automatically erasing historized portal data.
- **FR-026**: After disconnection, previously historized data MUST remain available and MUST be
  presented as historical/stale rather than live.
- **FR-027**: Disconnection MUST NOT affect unrelated portal functions or other connectors.
- **FR-028**: Purging a disconnected service's historized data MUST be a distinct, separately
  authorized, sensitive, audited action — never an automatic side effect of disconnection.

#### Compatibility
- **FR-029**: Before enabling or updating a connector, the system MUST check compatibility (portal
  version, dependencies, required capabilities, permissions, configuration) and MUST refuse or warn on
  incompatibility while preserving the previously working state.

#### Permissions & Audit
- **FR-030**: Connector operations MUST be gated by the authorization engine (deny-by-default,
  server-side), distinguishing read (`services.read`, `infrastructure.read`) from management
  (`services.manage`); destructive actions (purge, destructive resync, disconnection where configured
  sensitive) MUST be sensitive and audited.
- **FR-031**: Every sensitive connector action (enable/disable where configured sensitive, resync,
  disconnection, purge, compatibility override) MUST produce an audit entry with actor, action,
  timestamp, context, decision, and result where relevant.
- **FR-032**: Capability data exposed through connectors MUST respect consumer permissions and privacy;
  a connector MUST NOT become a path to bypass authorization or privacy.

#### Extensibility
- **FR-033**: Connectors MAY be provided by plugins; a plugin-provided connector MUST integrate into
  the same capability/state/sync model and MUST NOT, on failure, break unrelated connectors or portal
  functions.

### Connector State Model

**States**: Discovered (candidate), Configured, Enabled, Syncing, Error, Unavailable, Maintenance,
Disabled, Disconnected.

**Transitions** (actor in parentheses):

- Discovered to Configured (admin confirms a discovered candidate)
- (none) to Configured (admin configures manually)
- Configured to Enabled (admin enables, after a passing connection/compatibility check)
- Enabled to Syncing to Enabled (automatic/manual sync run, returning to Enabled on completion)
- Enabled to Error / Unavailable / Maintenance (service condition detected; historized data stays viewable)
- Error/Unavailable/Maintenance to Enabled (condition clears)
- Enabled/Error/Unavailable to Disabled (admin disables; capabilities withdrawn, data retained)
- Disabled to Enabled (admin re-enables)
- any connected state to Disconnected (admin disconnects; capabilities withdrawn, history retained)

**Invariants**:
- Disabling or disconnecting NEVER auto-erases historized data.
- Sync state (Syncing / last-run outcome) is distinct from service health (Enabled/Error/Unavailable).
- Capabilities are available only while Enabled (and not in a blocking Error/Unavailable condition).
- The external service remains the source of truth for native data in every state.

### Connector-Related Domain Events

Names aligned with the Event Model; each carries actor/context, service/connector reference,
metadata, and version.

- `service.connected`
- `service.disconnected`
- `service.status_changed`
- `sync.started`
- `sync.completed`
- `sync.failed`
- `connector.discovered` (candidate detected)
- `connector.compatibility_checked`
- `connector.resync_requested` (sensitive)
- `connector.data_purged` (sensitive; explicit, not automatic)

### Key Entities

- **Connector**: An external integration definition that declares the capabilities it can provide and
  how it is configured/tested; may be core or plugin-provided.
- **Service**: A concrete connected instance of a connector, with its own configuration, state, health,
  and sync history.
- **Capability**: A functional ability exposed to modules; the contract that decouples modules from
  concrete services. Multiple services may provide the same capability.
- **Connector State**: The lifecycle/health state of a service (see State Model).
- **SyncJob / Sync Run**: A synchronization execution with start, finish, outcome, counts, and errors;
  recorded in synchronization history.
- **Synchronization History**: The ordered record of sync runs for a service.
- **Conflict/Provenance Record**: Information used to resolve conflicting sources or preserve
  provenance.
- **Compatibility Check**: The evaluation of portal version, dependencies, capabilities, permissions,
  and configuration prior to enable/update.
- **Permission/Policy (referenced)**: Authorization inputs gating connector operations; owned by Roles
  & Permissions.
- **Domain Event / HistoryEntry (referenced)**: Produced into the global event/history backbone.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Adding a new service that provides an already-consumed capability requires changes to 0
  existing modules.
- **SC-002**: Modules reference a concrete service by name in 0% of capability consumption; 100% go
  through the capability contract.
- **SC-003**: Auto-discovered candidates are auto-enabled without explicit confirmation in 0% of cases.
- **SC-004**: A connection test reports an actionable result (pass or diagnosed failure) in 100% of
  runs and changes enable/disable state in 0% of runs.
- **SC-005**: Disabling or disconnecting a service auto-erases historized data in 0% of cases; after
  disconnection, previously historized data remains viewable (as stale) in 100% of cases.
- **SC-006**: Sync runs produce a history entry with outcome in 100% of runs; a sync failure breaks
  unrelated portal functions in 0% of cases.
- **SC-007**: Duplicate/late event delivery produces a non-idempotent result in 0% of sync consumers;
  attribution uses `occurred_at` in 100% of cases.
- **SC-008**: A full resync blindly destroys native portal data in 0% of runs; large-deletion resyncs
  require explicit confirmation in 100% of cases.
- **SC-009**: Conflicting sources are silently overwritten in 0% of cases (configured rule applied or
  provenance preserved in 100%).
- **SC-010**: 100% of sensitive connector actions (resync, disconnection, purge, compatibility
  override) produce an audit entry; sync state and service health are reported as distinct in 100% of
  service views.

## Assumptions

- The Services module's user-facing detail/supervision presentation (health metrics display, server
  operations UI) is owned by its own module spec; this spec owns the connector mechanics and the
  capability contract it exposes.
- The global event/history store and the audit facility are owned by their own Core specs; this spec
  produces events/history/audit into them.
- "Capability" granularity and the capability catalog are defined with each consuming domain; this
  spec fixes the contract behavior (declare/consume/resolve) rather than an exhaustive list.
- The scheduling of automatic sync (frequency, triggers) is configurable administrative policy; this
  spec requires its existence and historization, not fixed values. (Flagged as OQ-22.)
- Whether disconnection is itself always sensitive/audited or only when configured so is treated as
  policy, with purge always sensitive. (Related to OQ-21.)

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation.

- **OQ-20 (Multi-service capability resolution)**: Confirm how the portal selects among multiple
  services providing the same capability (admin priority, per-consumer choice, automatic failover) and
  whether consumers may request a specific provider.
- **OQ-21 (Disconnection vs purge authorization)**: Confirm whether plain disconnection is always a
  sensitive/audited action, and confirm the exact separate authorization required to purge a
  disconnected service's historized data.
- **OQ-22 (Sync scheduling model)**: Confirm whether automatic sync cadence is global, per-connector,
  or per-capability, and how manual sync interacts with it.
- **OQ-23 (Source-of-truth conflict policy)**: Confirm the default conflict-resolution policy
  (source-wins, newest-wins, preserve-provenance) and whether it is configurable per connector or per
  field.
- **OQ-24 (Discovery trust boundary)**: Confirm the scope/trust model for auto-discovery (what the
  portal is permitted to probe) to avoid probing services outside the operator's authority.

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference) and the project
  Constitution (v1.0.0).
- Composes with: `specs/003-roles-permissions/spec.md` (gating of connector operations;
  `services.read`/`services.manage`/`infrastructure.read`) and `specs/004-portal-core-shell/spec.md`
  (availability drives dynamic navigation; degraded-state presentation).
- Depends on / references: `architecture/FUNCTIONAL_ARCHITECTURE.md`, `architecture/EXTENSIBILITY.md`,
  `architecture/EVENT_MODEL.md`, `architecture/DATA_MODEL.md`, `product/BUSINESS_RULES.md`,
  `product/GLOSSARY.md`.
- Related specs (not owned here): the Services module spec (supervision/detail UI), the Synchronization
  Core spec (global sync semantics if separated), the Events & History Core spec (event/history store),
  and the Extensibility spec (023) (plugin-provided connectors).
