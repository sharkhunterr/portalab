# Feature Specification: Administration

**Feature Branch**: `020-administration`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Detailed functional specification of the Administration system — a Control Center, not a huge pile of settings."

## Role of This Document

This is a **detailed feature specification** for Administration — the single-Admin **Control Center**
that gives an at-a-glance picture of portal health and surfaces required actions, and from which every
administrable domain is governed (users, modules, plugins, connectors, services, content, support,
gamification, marketplace, statistics, notifications, AI, appearance, security, audit, infrastructure,
portal health, synchronization, automations). It also owns initial installation / first-run, config
preview/validation, sensitive-action handling, import/export, backup/restore, migration, updates, and
plugin compatibility. It conforms to and refines the superior reference specification
(`specs/001-portal-global-spec/spec.md`) and composes with Identity & Users
(`specs/002-identity-users/spec.md`), Roles & Permissions (`specs/003-roles-permissions/spec.md`), the
Portal Core shell (`specs/004-portal-core-shell/spec.md`), and every domain spec (005–019), under the
project Constitution (`.specify/memory/constitution.md`, v1.0.0). It draws on
`product/PRODUCT_BLUEPRINT.md` and `product/BUSINESS_RULES.md`.

### Control Center Principle (normative)

- Administration MUST be a **Control Center**: an overview that surfaces **state** and **required
  actions**, routing to focused management per domain — **NOT** a single giant undifferentiated settings
  dump.
- There is **exactly one Admin account**; Administration never creates a second Admin except via the
  explicit single-Admin transfer owned by Identity & Users; **no temporary delegation**.
- Administration **governs** each domain but **does not re-implement** it: it configures and operates the
  domain specs (Connectors, Services, Gamification, Marketplace, etc.) through their own rules (principle
  XX).
- Every **sensitive admin action** is **preview/validate-able where appropriate, confirmed, and
  audited**.

Scope boundary: this spec **owns** the admin Control Center (overview/dashboard, required-actions),
cross-domain admin operations (install/first-run, config preview/validate, enable/disable, import/export,
backup/restore, migration, update, plugin compatibility), and the admin audit surface. It **consumes**
each domain's own management rules and the authorization/event/notification engines. It chooses no
technology and contains no implementation detail.

**Terminology**: Control Center = the admin overview + routing surface; Required Action = a surfaced item
needing admin attention; Domain Event = a recorded fact.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Control Center overview with required actions (Priority: P1)

The Admin opens Administration and sees a Control Center: portal health, services, synchronizations,
incidents, tickets, automations, AI, infrastructure, storage, and — prominently — the actions that
require attention, each linking to the focused place to act.

**Why this priority**: The Control Center overview is the defining requirement; it turns administration
from a settings pile into an at-a-glance operations surface.

**Independent Test**: As the Admin, open the overview; confirm it shows portal/service/sync/incident/
ticket/automation/AI/infrastructure/storage status and a "required actions" area, each item navigating to
the focused management surface.

**Acceptance Scenarios**:

1. **Given** the Admin opens Administration, **When** the overview loads, **Then** it presents portal
   health, services, synchronizations, incidents, tickets, automations, AI, infrastructure, and storage
   status, each loading independently.
2. **Given** items need attention (e.g., a failed sync, a suspended automation, an open incident), **When**
   the overview loads, **Then** they appear as prioritized "required actions" linking to where to act.
3. **Given** a slow/unavailable source, **When** the overview loads, **Then** that panel shows its
   functional state while the rest of the Control Center remains usable.

### User Story 2 - Govern each administrable domain from a focused surface (Priority: P1)

From the Control Center, the Admin reaches focused management for each domain — users, modules, plugins,
connectors, services, content, support, gamification, marketplace, statistics, notifications, AI,
appearance, security, audit, infrastructure, portal health, synchronization, automations — operating each
through its own rules.

**Why this priority**: Breadth of governance is explicit; routing to focused surfaces (not one giant
page) realizes the Control Center principle.

**Independent Test**: For a representative subset of domains, navigate from the overview to its focused
management surface and perform one administrative operation; confirm it operates the domain through that
domain's rules and is audited where sensitive.

**Acceptance Scenarios**:

1. **Given** each administrable domain, **When** the Admin opens its management surface, **Then** it
   provides that domain's administrative operations (not a flattened settings dump).
2. **Given** a domain operation, **When** performed, **Then** it executes through the domain's own rules
   (e.g., connector enable/disable per Connectors; reward rules per Gamification) — no parallel mechanism.
3. **Given** a management action the Admin is not permitted (none normally, but scoped system actions),
   **When** attempted, **Then** authorization still applies server-side.

### User Story 3 - Single-Admin guarantee and sensitive-action handling (Priority: P1)

The portal has exactly one Admin; Administration enforces this and never allows a second Admin or
temporary delegation; sensitive admin actions are previewed/validated where appropriate, explicitly
confirmed, and audited.

**Why this priority**: The single-Admin rule and sensitive-action discipline are locked and central to
administration's integrity.

**Independent Test**: Confirm exactly one Admin; attempt to create a second / delegate (refused); perform
a sensitive action (e.g., delete, economy-rule change) and confirm preview/validate + confirmation +
audit.

**Acceptance Scenarios**:

1. **Given** one Admin exists, **When** creating a second Admin or temporarily delegating is attempted,
   **Then** it is refused (Admin transfer, owned by Identity & Users, is the only path and keeps exactly
   one).
2. **Given** a sensitive admin action, **When** initiated, **Then** it offers a preview/validation where
   appropriate, requires explicit confirmation, and is audited (actor, action, timestamp, context,
   result).
3. **Given** any admin action, **When** performed, **Then** it is recorded; destructive/irreversible ones
   carry a clear warning and confirmation.

### User Story 4 - Initial installation & first-run wizard (Priority: P1)

On a fresh portal, an installation / first-run wizard guides initial configuration, establishes the
single Admin, and brings the portal to a usable baseline without requiring manual low-level setup.

**Why this priority**: First-run determines a correct, secure starting state (including establishing the
sole Admin) and is explicitly required.

**Independent Test**: Run first-run on a fresh portal; confirm it establishes exactly one Admin, captures
essential configuration, validates it, and results in a usable baseline with no dead-ends.

**Acceptance Scenarios**:

1. **Given** a fresh portal, **When** the first-run wizard runs, **Then** it establishes exactly one Admin
   and captures the essential initial configuration.
2. **Given** wizard inputs, **When** submitted, **Then** they are validated before being applied, with
   clear errors on invalid input.
3. **Given** the wizard completes, **When** finished, **Then** the portal is in a usable baseline state
   and the first-run cannot be trivially re-run to create another Admin.

### User Story 5 - Configuration with preview and validation (Priority: P2)

The Admin changes configuration (global/module/plugin defaults within the hierarchy); changes can be
previewed and are validated before applying, with the configuration hierarchy (Global → Module → Plugin →
User) respected.

**Why this priority**: Preview/validation prevents misconfiguration; respecting the hierarchy keeps admin
policy, plugin behavior, and user preference composable.

**Independent Test**: Change a configuration value with a preview; submit invalid input (rejected with
reason); apply valid input and confirm it takes effect at the correct hierarchy level.

**Acceptance Scenarios**:

1. **Given** a configuration change, **When** previewed, **Then** the Admin can see its effect before
   applying.
2. **Given** invalid configuration, **When** validated, **Then** it is rejected with an actionable reason
   and not applied.
3. **Given** a valid change, **When** applied, **Then** it takes effect at the correct hierarchy level and
   user preferences remain retained where still permitted.

### User Story 6 - Enable/disable modules, plugins, connectors, services, automations (Priority: P1)

The Admin enables/disables modules, plugins, connectors, services, and automations; disabling never
deletes data, navigation updates dynamically, and a disabled extension's failure cannot break the portal.

**Why this priority**: Enable/disable is a core admin lever tied to locked rules (disable ≠ delete;
plugin isolation; dynamic navigation).

**Independent Test**: Disable a module/plugin/connector/automation; confirm it stops being offered/active,
its data persists, navigation updates, and the portal stays healthy; re-enable and confirm restoration.

**Acceptance Scenarios**:

1. **Given** an enabled module/plugin/connector/service/automation, **When** disabled, **Then** it stops
   being active/offered, its data is retained, and navigation updates dynamically.
2. **Given** a disabled extension, **When** re-enabled (subject to compatibility), **Then** it is restored.
3. **Given** a disabled or failing extension, **When** the portal runs, **Then** unrelated functions are
   unaffected (isolation).

### User Story 7 - Import/export, backup/restore, migration, update, plugin compatibility (Priority: P1)

The Admin can export/import configuration, back up and restore portal state, run data migrations, apply
updates, and check plugin compatibility — each validated, previewed where appropriate, confirmed, audited,
and integrity-preserving.

**Why this priority**: These are high-impact lifecycle operations; they must preserve integrity (no blind
data destruction) and be reversible/verifiable where possible.

**Independent Test**: Export then import config; take a backup and restore it; run a migration and an
update with compatibility checks; confirm each validates, warns on risk, is audited, and preserves
historical/transaction integrity.

**Acceptance Scenarios**:

1. **Given** configuration, **When** exported and re-imported, **Then** it validates and applies without
   corrupting existing data; conflicts are surfaced, not silently overwritten.
2. **Given** a backup, **When** restored, **Then** the restore is validated and confirmed; it preserves
   historical/transaction integrity and does not blindly destroy newer native data without explicit
   confirmation.
3. **Given** a migration or update, **When** run, **Then** compatibility (portal version, dependencies,
   plugin compatibility) is checked first; incompatible items are refused/warned, and the operation is
   audited.
4. **Given** a plugin, **When** its compatibility is checked, **Then** portal version, dependencies,
   capabilities, permissions, and configuration are verified before activation/update.

### User Story 8 - Portal health, infrastructure, storage, and audit surfaces (Priority: P2)

The Admin monitors portal health, infrastructure, and storage, and reviews the audit trail of sensitive
actions across the portal, all within permissions and privacy.

**Why this priority**: Health/infra/storage visibility and a trustworthy audit surface are core to safe
operation and accountability.

**Independent Test**: View portal health, infrastructure, and storage; review the audit trail; confirm
sensitive actions appear with actor/action/time/context/result and that private data is not exposed
beyond policy.

**Acceptance Scenarios**:

1. **Given** the Admin, **When** viewing portal health/infrastructure/storage, **Then** current state and
   trends are shown with functional states, degrading gracefully on partial failure.
2. **Given** the audit surface, **When** reviewed, **Then** sensitive actions across domains are listed
   (actor, action, timestamp, context, result), append-only and not rewritten.
3. **Given** audit/health data, **When** viewed, **Then** it respects privacy and never exposes secrets.

### Edge Cases

- **Attempt to create a second Admin**: Refused; the only path is the Identity & Users single-Admin
  transfer that keeps exactly one Admin; no temporary delegation.
- **Sole Admin tries to delete/demote themselves**: Refused unless Admin is first transferred (per
  Identity & Users), so the portal is never left with zero Admins.
- **Sensitive action without confirmation**: Not performed; preview/validation and explicit confirmation
  are required.
- **Invalid configuration**: Rejected at validation with an actionable reason; not partially applied.
- **Disable that would orphan data**: Disabling never deletes data; data persists and is restorable on
  re-enable.
- **Restore over newer data**: A restore that would overwrite newer native data requires explicit
  confirmation and never blindly destroys it (consistent with Connectors/Events resync rules).
- **Incompatible plugin/update**: Refused or warned by the compatibility check; the previously working
  state is preserved.
- **Migration failure mid-run**: Integrity preserved; the operation is recoverable/auditable and does not
  leave data corrupted.
- **Import conflict**: Surfaced for resolution (source-of-truth/provenance), never silently overwritten.
- **First-run re-run attempt**: Cannot be trivially re-run to create another Admin or reset the portal
  without explicit, audited authorization.
- **Overview source unavailable**: The affected panel shows its state; the Control Center and other
  panels remain usable (graceful degradation).
- **Admin action audit privacy**: Audit records what is needed (actor/action/time/context/result) without
  leaking secrets or unnecessary PII.
- **AI/automation admin surfaces**: Governed here but operated through the AI/Automations specs (no
  parallel control logic).

## Requirements *(mandatory)*

### Functional Requirements

#### Control Center Overview
- **FR-001**: Administration MUST present a Control Center overview showing portal health, services,
  synchronizations, incidents, tickets, automations, AI, infrastructure, and storage status, each loading
  independently.
- **FR-002**: The overview MUST surface prioritized "required actions" (items needing attention) each
  linking to the focused place to act.
- **FR-003**: The overview MUST degrade gracefully: a slow/unavailable panel shows its functional state
  without blocking the rest.
- **FR-004**: Administration MUST route to focused per-domain management surfaces rather than a single
  undifferentiated settings page (Control Center, not a settings dump).

#### Domain Governance (without re-implementation)
- **FR-005**: Administration MUST provide administrative operations for each domain: Users, Modules,
  Plugins, Connectors, Services, Content, Support, Gamification, Marketplace, Statistics, Notifications,
  AI, Appearance, Security, Audit, Infrastructure, Portal Health, Synchronization, and Automations.
- **FR-006**: Each domain operation MUST execute through that domain's own rules/spec (no parallel
  mechanism), and MUST be gated server-side by the authorization engine.

#### Single-Admin & Sensitive Actions
- **FR-007**: The portal MUST have exactly one Admin; Administration MUST NOT create a second Admin or
  allow temporary delegation; the single-Admin transfer (Identity & Users) is the only path and keeps
  exactly one Admin.
- **FR-008**: Sensitive admin actions MUST offer preview/validation where appropriate, require explicit
  confirmation, and be audited (actor, action, timestamp, context, result).
- **FR-009**: Destructive/irreversible admin actions MUST carry a clear warning and explicit confirmation
  and MUST NOT proceed without it.

#### Installation & First-Run
- **FR-010**: A first-run/installation wizard MUST establish exactly one Admin and capture essential
  initial configuration on a fresh portal, resulting in a usable baseline with no dead-ends.
- **FR-011**: First-run inputs MUST be validated before applying; the wizard MUST NOT be trivially
  re-runnable to create another Admin or reset the portal without explicit, audited authorization.

#### Configuration (preview & validation, hierarchy)
- **FR-012**: Configuration changes MUST support preview (seeing the effect before applying) where
  appropriate and MUST be validated before applying, rejecting invalid input with an actionable reason.
- **FR-013**: Configuration MUST respect the hierarchy (Global → Module → Plugin → User); admin policy
  MAY constrain lower levels while user preferences are retained where still permitted.

#### Enable / Disable
- **FR-014**: Administration MUST allow enabling/disabling modules, plugins, connectors, services, and
  automations; disabling MUST NOT delete data and navigation MUST update dynamically.
- **FR-015**: A disabled or failing extension MUST be isolated so it does not break unrelated portal
  functions; re-enabling MUST be subject to compatibility checks.

#### Import/Export, Backup/Restore, Migration, Update, Compatibility
- **FR-016**: Administration MUST support configuration export and import; imports MUST be validated and
  MUST surface conflicts (source-of-truth/provenance) rather than silently overwriting.
- **FR-017**: Administration MUST support backup and restore; restores MUST be validated and confirmed,
  MUST preserve historical/transaction integrity, and MUST NOT blindly destroy newer native data without
  explicit confirmation.
- **FR-018**: Administration MUST support data migrations that preserve historical integrity and are
  recoverable/auditable on failure (no silent corruption).
- **FR-019**: Administration MUST support applying updates with a compatibility check (portal version,
  dependencies) beforehand; incompatible updates MUST be refused/warned and the prior state preserved.
- **FR-020**: Administration MUST check plugin compatibility (portal version, dependencies, capabilities,
  permissions, configuration) before activation/update.

#### Portal Health, Infrastructure, Storage, Audit
- **FR-021**: Administration MUST present portal health, infrastructure, and storage status/trends with
  functional states, degrading gracefully on partial failure, within permissions.
- **FR-022**: Administration MUST provide an audit surface listing sensitive actions across domains
  (actor, action, timestamp, context, result), append-only and never rewritten.
- **FR-023**: Health/infrastructure/storage/audit surfaces MUST respect privacy and MUST NOT expose
  secrets.

#### Cross-Cutting (events, notifications, resilience)
- **FR-024**: Administrative actions MUST emit domain events with `occurred_at` distinct from
  `received_at`; consumers MUST be idempotent where duplicates are possible.
- **FR-025**: Admin notifications (required actions, suspensions, failures, update availability) MUST be
  produced via the notification engine, respecting preferences (no parallel mechanism).
- **FR-026**: The Administration surfaces MUST themselves remain usable under partial failure (the Control
  Center never fully fails because one domain source is down).

### Administrable Domains Map (governed, not re-implemented)

Each links to the owning spec; Administration configures/operates via that spec's rules:

- **Users** → Identity & Users (002) · **Security/Roles** → Roles & Permissions (003)
- **Modules/Shell** → Portal Core (004) · **Connectors** → (005) · **Services/Infrastructure/Portal
  Health** → Services & Health (006)
- **Synchronization** → Connectors (005) / Events & History (007) · **Audit/Events** → Events & History
  (007) + Permissions (003)
- **Notifications** → (010) · **Content (News/Wiki/Calendar)** → (011) · **Community** → (012)
- **Gamification/Economy** → (013) · **Appearance/Themes** → Personalization/Themes/A11y (022) ·
  **Marketplace** → (015)
- **Support** → (016) · **Statistics** → (017) · **AI** → (018) · **Automations** → (019)
- **Plugins/Extensibility** → Extensibility (023) · **Media** → (024) · **Portal Observability** → (025)
  · **i18n** → (026)

### Admin Dashboard Panels (required)

Portal health · Services · Synchronizations · Incidents · Tickets · Automations · AI · Infrastructure ·
Storage · **Required Actions** (prioritized, actionable).

### Administration-Related Domain Events

- `admin.config_changed`, `admin.module_toggled`, `admin.plugin_toggled`, `admin.connector_toggled`
- `admin.backup_created`, `admin.restore_performed`, `admin.migration_run`, `admin.update_applied`
- `admin.import_performed`, `admin.export_performed`, `admin.firstrun_completed`
- `user.admin_transferred` (referenced; owned by Identity & Users)
- Domain effects reuse the owning domains' events.

### Key Entities

- **Control Center Overview**: The admin landing surface aggregating status + required actions.
- **Required Action**: A prioritized, actionable item surfaced for admin attention, linking to its
  focused surface.
- **Admin Management Surface**: A focused per-domain administration view operating that domain's rules.
- **Configuration Change**: A previewable/validated change at a hierarchy level (Global/Module/Plugin).
- **First-Run/Installation**: The initial setup flow establishing the single Admin and baseline config.
- **Backup / Restore / Migration / Update / Import / Export**: Lifecycle operations, validated,
  confirmed, audited, integrity-preserving.
- **Compatibility Check**: The verification before activating/updating a plugin/connector/update.
- **Audit Surface**: The append-only view of sensitive actions across domains.
- **Admin Account (referenced)**: The single Admin; transfer owned by Identity & Users.
- **Owning domain specs (referenced)**: 002–019 governed here, not re-implemented.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The overview presents all required panels (health/services/sync/incidents/tickets/
  automations/AI/infrastructure/storage) plus required actions in 100% of loads, each loading
  independently.
- **SC-002**: Administration presents a single undifferentiated settings dump in 0% of cases (Control
  Center routing to focused surfaces in 100%).
- **SC-003**: Administration creates a second Admin or allows temporary delegation in 0% of cases; exactly
  one Admin is maintained in 100% of states.
- **SC-004**: Sensitive admin actions proceed without preview/validation-where-appropriate + confirmation
  + audit in 0% of cases.
- **SC-005**: First-run establishes exactly one Admin and a usable baseline in 100% of fresh installs; it
  is trivially re-runnable to create another Admin in 0% of cases.
- **SC-006**: Invalid configuration is applied in 0% of cases (rejected at validation); valid changes take
  effect at the correct hierarchy level in 100% of cases.
- **SC-007**: Disabling a module/plugin/connector/automation deletes data in 0% of cases; navigation
  updates dynamically in 100% of cases.
- **SC-008**: Restores/migrations blindly destroy newer native data without explicit confirmation in 0% of
  cases; historical/transaction integrity is preserved in 100% of cases.
- **SC-009**: Incompatible plugins/updates are activated/applied in 0% of cases (compatibility checked
  first in 100%).
- **SC-010**: 100% of sensitive admin actions appear in the append-only audit surface; audit entries are
  rewritten in 0% of cases.

## Assumptions

- Each administrable domain is owned by its own spec (002–026, incl. Personalization/Themes/A11y 022 and
  Extensibility 023);
  Administration governs via those rules and does not re-implement them.
- The single-Admin account lifecycle and transfer are owned by Identity & Users; Administration enforces
  the consequence (never a second Admin, no delegation).
- The authorization, event/history, audit, and notification engines are owned by their specs.
- The exact backup/restore/migration/update mechanics (scope, scheduling, retention) are configurable
  operational policy. (Flagged as OQ-96/OQ-97.)
- The precise set and prioritization of "required actions" is configurable/derived from domain states.
  (Flagged as OQ-95.)

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation.

- **OQ-95 (Required-actions model)**: Confirm which conditions generate a "required action", how they are
  prioritized, and when they clear.
- **OQ-96 (Backup/restore scope & retention)**: Confirm what a backup covers (config only vs full portal
  state incl. history/ledger), retention, and restore-conflict handling with newer native data.
- **OQ-97 (Update/migration model)**: Confirm how updates/migrations are delivered and sequenced, and the
  rollback/recovery expectations on failure.
- **OQ-98 (First-run re-run / reset policy)**: Confirm the exact safeguards preventing first-run re-run
  and whether a controlled factory-reset exists (and its authorization).
- **OQ-99 (Appearance/Theming admin scope) — RESOLVED (CD-022)**: Personalization/Themes/A11y (022) owns
  presentation; Administration's Appearance only configures within policy (presentation-only guarantees
  per CD-022).

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference) and the project
  Constitution (v1.0.0).
- Composes with: `specs/002-identity-users/spec.md` (single-Admin lifecycle/transfer; Users admin),
  `specs/003-roles-permissions/spec.md` (server-side gating; audit; Security), `specs/004-portal-core-shell/spec.md`
  (dynamic navigation on enable/disable; degraded states), and every domain spec 005–026 (governed via
  their own rules).
- Depends on / references: `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`,
  `architecture/EXTENSIBILITY.md`, `architecture/EVENT_MODEL.md`, `architecture/DATA_MODEL.md`.
- Related specs (not owned here): Personalization/Themes/A11y spec (022) (Appearance), the Extensibility
  spec (023) (Plugins/compatibility), Observability (025) (portal health/infra signals), and the Privacy
  spec (021) (visibility in admin surfaces).
