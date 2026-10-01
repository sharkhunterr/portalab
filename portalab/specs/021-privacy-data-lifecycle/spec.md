# Feature Specification: Privacy, Data Management & Lifecycle

**Feature Branch**: `021-privacy-data-lifecycle`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Detailed functional specification of Privacy, Data Management & Lifecycle."

## Role of This Document

This is a **detailed feature specification** for Privacy, Data Management & Lifecycle — the transversal
system that classifies data, owns the visibility engine (levels + admin overrides that preserve/restore
user preference), governs retention/export/deletion/anonymization, and defines how source-of-truth,
service disconnection, external-data deletion, and aggregate data interact with privacy. It conforms to
and refines the superior reference specification (`specs/001-portal-global-spec/spec.md`) and composes
with Identity & Users (`specs/002-identity-users/spec.md`), Roles & Permissions
(`specs/003-roles-permissions/spec.md`), Connectors (`specs/005-connectors/spec.md`), Events & History
(`specs/007-events-history/spec.md`), Gamification & Economy (`specs/013-gamification-economy/spec.md`),
and Administration (`specs/020-administration/spec.md`), under the project Constitution
(`.specify/memory/constitution.md`, v1.0.0). It draws on `product/PRODUCT_BLUEPRINT.md`,
`product/BUSINESS_RULES.md`, and `architecture/DATA_MODEL.md`.

Scope boundary: this spec **owns** the **visibility engine** (levels, admin override preserve/restore),
data classification, the privacy composition rule (privacy gates independently of permission),
retention, export, deletion/anonymization lifecycle, and the privacy aspects of source-of-truth, service
disconnection, external-data deletion, and aggregate data. It is the authoritative definition that the
Identity & Users deletion lifecycle, Roles & Permissions privacy composition, and other specs **reference
and must not contradict**. It **consumes** the authorization engine (permission is a separate gate), the
event/history store, and the economy ledger (Coin destruction at deletion). It chooses no technology and
contains no implementation detail.

### Normative Privacy Invariants

- **Historized ≠ public.** Data being recorded in history NEVER makes it public.
- **Privacy is independent from permission.** Having permission to read a class of data NEVER overrides
  another user's visibility/privacy preference.
- **Visibility levels**: **Public**, **Community**, **Leaderboards only**, **Private**.
- **Admin temporary visibility override** preserves the user's previous preference; when the override is
  removed, the original preference is **automatically restored**.
- **Final deletion**: personal data deleted/anonymized; **Coins destroyed**; historical integrity
  preserved; aggregate statistics may be kept when necessary and non-identifying.

**Terminology**: Visibility = who may see a datum (levels above); Permission = whether an actor may
perform an action (Roles & Permissions); Anonymization = severing identifiability while preserving
integrity-necessary records; Domain Event = a recorded fact.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Visibility levels honored independently of permission (Priority: P1)

A user sets the visibility of their data (Public, Community, Leaderboards only, Private); the portal shows
each datum only to the allowed audience, and a viewer's permission to read a class of data never overrides
another user's visibility preference.

**Why this priority**: Visibility + the "permission ≠ privacy" rule is the foundation of the whole system
and the highest data-exposure risk.

**Independent Test**: Set a field to each visibility level; view as different audiences (self, community
member, leaderboard context, outsider) and as a high-permission viewer; confirm each sees only what the
level allows and that permission alone never reveals Private data.

**Acceptance Scenarios**:

1. **Given** a datum set to Private, **When** anyone (including a high-permission viewer) looks, **Then**
   it is not shown by permission alone.
2. **Given** a datum set to Community, **When** a community member views it, **Then** it is shown; **When**
   an outsider views it, **Then** it is not.
3. **Given** a datum set to Leaderboards only, **When** a leaderboard is rendered, **Then** the datum may
   appear there while remaining hidden on the full profile per the level.
4. **Given** a datum set to Public, **When** anyone permitted to reach the surface views it, **Then** it is
   shown (subject to any admin policy).

### User Story 2 - Admin temporary visibility override that preserves & restores preference (Priority: P1)

An admin can impose a temporary visibility (e.g., force a profile Private); the user's previous preference
is preserved; when the override is removed, the original preference is restored automatically.

**Why this priority**: This exact preserve-and-restore behavior is a locked decision and a subtle,
high-impact correctness requirement.

**Independent Test**: Record a user's preference; apply an admin override to a different visibility;
confirm the override is in effect and the preference is preserved (not overwritten); remove the override
and confirm the original preference is automatically restored.

**Acceptance Scenarios**:

1. **Given** a user preference and an admin override, **When** the override is applied, **Then** the
   effective visibility is the override while the user's underlying preference is preserved unchanged.
2. **Given** an active override, **When** it is removed, **Then** the user's original preference is
   automatically restored as the effective visibility.
3. **Given** an override, **When** applied/removed, **Then** both actions are audited (admin action) and
   the user's preference is never silently overwritten or lost.
4. **Given** an override and the priority order (Security/Permissions > Data Integrity > Privacy > Business
   Rules > Admin Config > User Preferences > Presentation), **When** resolved, **Then** admin policy
   constrains visibility while the preference is retained for restoration.

### User Story 3 - Data classification governs handling (Priority: P1)

The system classifies data as personal, activity, or technical (plus history/audit/aggregate), and each
class is handled per its rules for visibility, retention, export, and deletion/anonymization.

**Why this priority**: Correct classification drives every downstream privacy behavior (what is exported,
deleted, retained, anonymized).

**Independent Test**: Tag representative data of each class; confirm export includes the right classes,
deletion/anonymization treats each per its rule, and retention applies per class.

**Acceptance Scenarios**:

1. **Given** personal, activity, and technical data (and history/audit/aggregate), **When** handled,
   **Then** each is treated per its classification for visibility/retention/export/deletion.
2. **Given** historized data, **When** classified, **Then** it is not public by default regardless of
   class.
3. **Given** audit data, **When** handled, **Then** it is append-only and treated distinctly from general
   activity data.

### User Story 4 - Export personal data (Priority: P1)

A user exports the data the portal holds about them — personal, activity, and their attributable
historized representations — excluding other users' private data and secrets.

**Why this priority**: Export is a locked privacy capability and a prerequisite for informed deletion
(consistent with Identity & Users).

**Independent Test**: Request an export; confirm it includes the requester's personal/activity/history
data, excludes others' private data and secrets, and is recorded.

**Acceptance Scenarios**:

1. **Given** a user, **When** they export their data, **Then** it includes their personal and activity
   data and attributable historized representations.
2. **Given** an export, **When** produced, **Then** it excludes other users' private data and any secrets,
   and the export is recorded (`user.data_exported`).

### User Story 5 - Deletion → anonymization → final deletion (Priority: P1)

Account/data deletion follows the lifecycle: pending deletion (grace period, cancellable), then final
deletion where personal data is deleted/anonymized, Coins destroyed, historical integrity preserved, and
aggregate statistics possibly retained when necessary and non-identifying.

**Why this priority**: This encodes multiple locked rules with legal/trust weight; it is the authoritative
definition the Identity & Users spec references.

**Independent Test**: Run the lifecycle; confirm pending deletion is cancellable, and at final deletion
personal data is removed/anonymized, Coins destroyed via a recorded transaction, integrity history
preserved, aggregates retained only when non-identifying, and nothing private becomes public.

**Acceptance Scenarios**:

1. **Given** a deletion request, **When** in the grace period, **Then** it is cancellable and restores the
   prior state (consistent with Identity & Users).
2. **Given** final deletion, **When** it runs, **Then** personal data is deleted or anonymized such that
   the user is no longer identifiable.
3. **Given** final deletion, **When** it runs, **Then** remaining Coins are destroyed via a recorded
   economy transaction and historical transaction integrity is preserved.
4. **Given** final deletion, **When** it runs, **Then** aggregate statistics may be retained only when
   necessary and non-identifying, and no previously private data becomes public as a result.

### User Story 6 - Retention governs lifecycle without breaking integrity (Priority: P2)

Data is retained per configurable retention policy by class; retention cleanup never deletes
integrity-necessary records (e.g., economy transactions) and never makes private data public.

**Why this priority**: Retention ties classification to lifecycle; mishandling loses integrity data or
over-retains personal data.

**Independent Test**: Apply a retention policy; confirm data beyond the window is handled per policy while
integrity-necessary records persist and nothing private is exposed.

**Acceptance Scenarios**:

1. **Given** a retention policy per class, **When** it applies, **Then** data beyond the window is handled
   per policy without deleting integrity-necessary records.
2. **Given** retention cleanup, **When** it runs, **Then** it never makes private/historized data public
   and never breaks referential/transaction integrity.

### User Story 7 - Source of truth, service disconnection, external-data deletion (Priority: P1)

External services remain the source of truth for native data; disconnecting a service removes live
access/sync but does not auto-erase portal history; deleting external data at the source reconciles the
portal representation per rules without destroying unrelated portal-native data.

**Why this priority**: These are locked data-integrity rules at the boundary of privacy and connectors;
mishandling destroys user data or misrepresents provenance.

**Independent Test**: Disconnect a service (confirm history retained, marked historical); delete a datum at
the source (confirm the portal representation reconciles per rules, provenance preserved, unrelated native
data intact).

**Acceptance Scenarios**:

1. **Given** a connected service, **When** disconnected, **Then** live access/sync stops but historized
   portal data is not automatically erased (consistent with Connectors).
2. **Given** a datum deleted at the source, **When** reconciled, **Then** the portal representation updates
   per source-of-truth rules while preserving provenance and not destroying unrelated portal-native data.
3. **Given** a purge of a disconnected service's data, **When** requested, **Then** it is a distinct,
   separately authorized, audited action — never an automatic side effect of disconnection.

### User Story 8 - Aggregate data and privacy-safe analytics (Priority: P2)

Aggregate/statistical data derived from users is handled so it does not de-anonymize individuals; it may
be retained when non-identifying and necessary, even after an individual's deletion.

**Why this priority**: Aggregates are explicitly retainable but must never become a back door to
individual data.

**Independent Test**: Produce aggregates; confirm they do not expose or reconstruct an individual's private
data (small-sample protection), and that they may persist post-deletion when non-identifying.

**Acceptance Scenarios**:

1. **Given** aggregate statistics, **When** viewed, **Then** they do not de-anonymize or expose an
   individual's private data by permission alone.
2. **Given** an individual's deletion, **When** aggregates are retained, **Then** only non-identifying,
   necessary aggregates persist; identifying contributions are removed/anonymized.

### Edge Cases

- **Permission vs privacy**: A high-permission viewer still cannot see another user's Private data by
  permission alone; privacy gates independently.
- **Override while preference changes**: If the user changes their preference while an admin override is
  active, the new preference is stored as the underlying preference and restored when the override is
  removed (never lost). (See OQ-100.)
- **Nested/stacked overrides**: Only one effective admin visibility applies; removing it restores the
  user preference, not a prior override. (See OQ-100.)
- **Historized ≠ public**: No classification, theme, default, or aggregate ever makes historized/private
  data public automatically.
- **Deletion during active override**: Final deletion removes/anonymizes personal data regardless of
  override; the override and preference records are removed with the personal data.
- **Coins at deletion**: Remaining Coins destroyed via a recorded transaction; no real-value refund;
  ledger integrity preserved and anonymized.
- **Disconnection ≠ erasure**: Disconnecting a service never auto-erases portal history; purge is a
  separate, authorized, audited action.
- **External delete vs portal-native data**: Reconciling a source deletion never destroys unrelated
  portal-native data; provenance preserved.
- **Aggregate de-anonymization risk**: Small-sample/aggregate outputs must not allow reconstructing an
  individual's private data. (See OQ-102.)
- **Export of mixed-ownership data**: An export contains only the requester's data; shared/other-user
  private data is excluded or redacted.
- **Retention vs legal/integrity holds**: Integrity-necessary records (transactions, audit) survive
  retention cleanup; deletion anonymizes rather than destroys where integrity requires.
- **Anonymized data re-identification**: Anonymized records must not be re-identifiable via joins with
  retained data.

## Requirements *(mandatory)*

### Functional Requirements

#### Visibility Engine (levels + composition)
- **FR-001**: The system MUST support visibility levels Public, Community, Leaderboards only, and Private
  for user-controlled data.
- **FR-002**: Visibility MUST be enforced server-side so a datum is shown only to its allowed audience;
  permission to read a class of data MUST NOT override another user's visibility/privacy preference.
- **FR-003**: "Leaderboards only" MUST allow a datum to appear in leaderboard contexts while remaining
  hidden on fuller surfaces per the level.
- **FR-004**: The system MUST resolve visibility consistently with the product priority order
  (Security/Permissions > Data Integrity > Privacy > Business Rules > Admin Config > User Preferences >
  Presentation).

#### Admin Override (preserve & restore)
- **FR-005**: An admin MUST be able to impose a temporary visibility override on a user's data.
- **FR-006**: An override MUST preserve the user's previous preference unchanged (never overwrite/lose it).
- **FR-007**: When an override is removed, the user's original preference MUST be automatically restored as
  the effective visibility.
- **FR-008**: Applying/removing an override MUST be audited as an admin action; only one effective admin
  visibility MUST apply at a time.

#### Data Classification
- **FR-009**: The system MUST classify data as at least personal, activity, and technical, plus
  history, audit, and aggregate, and MUST handle each per its class for visibility/retention/export/
  deletion.
- **FR-010**: Historized data MUST NOT be public by default regardless of class; audit data MUST be
  append-only and distinct from general activity data.

#### Export
- **FR-011**: A user MUST be able to export the data the portal holds about them (personal, activity, and
  attributable historized representations).
- **FR-012**: An export MUST exclude other users' private data and any secrets, and MUST be recorded.

#### Deletion Lifecycle (pending → anonymization → final)
- **FR-013**: Deletion MUST follow a lifecycle with a cancellable grace period (pending deletion),
  consistent with Identity & Users.
- **FR-014**: At final deletion, personal data MUST be deleted or anonymized such that the user is no
  longer identifiable.
- **FR-015**: At final deletion, remaining Coins MUST be destroyed via a recorded economy transaction (no
  real-value refund) and historical transaction integrity MUST be preserved.
- **FR-016**: At final deletion, aggregate statistics MAY be retained only when necessary and
  non-identifying; no previously private data MUST become public as a result.
- **FR-017**: Final deletion MUST be irreversible; anonymized records MUST NOT be re-identifiable via joins
  with retained data.

#### Retention
- **FR-018**: Data MUST be retained per a configurable retention policy by class; retention cleanup MUST
  NOT delete integrity-necessary records (e.g., economy transactions, audit).
- **FR-019**: Retention cleanup MUST NEVER make private/historized data public and MUST preserve
  referential/transaction integrity.

#### Source of Truth, Disconnection, External Deletion
- **FR-020**: External services MUST remain the source of truth for their native data; the portal MUST
  store only the representations/history it needs.
- **FR-021**: Disconnecting a service MUST stop live access/sync WITHOUT automatically erasing historized
  portal data (consistent with Connectors); purge MUST be a distinct, separately authorized, audited
  action.
- **FR-022**: When a datum is deleted at the source, the portal representation MUST reconcile per
  source-of-truth rules while preserving provenance and NOT destroying unrelated portal-native data.

#### Aggregate Data
- **FR-023**: Aggregate/statistical outputs MUST NOT de-anonymize or expose an individual's private data by
  permission alone (privacy-safe aggregation, e.g., minimum-sample protection).
- **FR-024**: After an individual's deletion, only non-identifying necessary aggregates MAY persist;
  identifying contributions MUST be removed/anonymized.

#### Cross-Cutting (permissions, audit, events)
- **FR-025**: Privacy decisions MUST compose with the authorization engine: authorization gates access
  first, privacy further restricts; neither silently overrides the other.
- **FR-026**: Sensitive privacy/data actions (override apply/remove, export, deletion steps, purge,
  retention changes) MUST be audited (actor, action, timestamp, context, result), append-only.
- **FR-027**: Privacy/data lifecycle actions MUST emit domain events (e.g., `user.data_exported`,
  `user.anonymized`, `user.deleted`, visibility override events) with `occurred_at` distinct from
  `received_at`; consumers MUST be idempotent where duplicates are possible.

### Visibility Model

**Levels** (narrowing audience): Public → Community → Leaderboards only → Private.

**Effective visibility resolution**:
- Start from the user's **preference** per datum/class.
- If an **admin override** is active, the **override** is the effective visibility; the preference is
  preserved separately.
- On override removal, the **preference** becomes effective again (automatic restore).
- Permission is a separate gate applied independently; the stricter of (permission-allows AND
  visibility-allows) governs what is shown.

### Admin Override Model

- **State**: `preference` (user's own) + optional `active_override` (admin-set, temporary).
- **Apply override**: set `active_override`; `preference` untouched; audited.
- **Change preference while overridden**: update `preference` (stored); effective stays the override.
- **Remove override**: clear `active_override`; effective = `preference` (automatic restore); audited.
- **Invariant**: `preference` is never overwritten or lost by an override.

### Deletion Lifecycle Model

**Stages**: Active → Pending Deletion (grace period, cancellable) → Final Deletion (terminal).

At **Final Deletion**:
- Personal data deleted/anonymized (no longer identifiable).
- Coins destroyed via recorded transaction.
- Historical/transaction integrity preserved (anonymized subject).
- Aggregates retained only if non-identifying and necessary.
- Nothing private becomes public; anonymized data not re-identifiable.

### Privacy/Data-Related Domain Events

- `privacy.visibility_changed` (user preference), `privacy.override_applied`, `privacy.override_removed`
- `user.data_export_requested`, `user.data_exported`
- `user.deletion_requested`, `user.deletion_cancelled`, `user.anonymized`, `user.deleted`
- `privacy.retention_applied`, `service.data_purged` (referenced; separately authorized)

### Key Entities

- **Data Classification**: personal / activity / technical / history / audit / aggregate, each with
  handling rules.
- **Visibility Preference**: a user's chosen level (Public/Community/Leaderboards-only/Private) per datum/
  class.
- **Admin Visibility Override**: a temporary admin-set effective visibility that preserves the preference.
- **Effective Visibility**: the resolved level (override if active, else preference), composed with
  permission.
- **Retention Policy**: per-class rules governing lifecycle without breaking integrity.
- **Export**: the requester-scoped data copy.
- **Deletion Request / Anonymization**: the lifecycle record and the identifiability-severing operation.
- **Aggregate Dataset**: non-identifying statistical data that may persist post-deletion.
- **Provenance Record**: source-of-truth/origin information preserved across reconciliation.
- **AuditEntry / Domain Event (referenced)**: append-only records of privacy actions.
- **Permission (referenced)**: the separate authorization gate (Roles & Permissions).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Permission alone reveals another user's Private data in 0% of cases (privacy gates
  independently).
- **SC-002**: Each visibility level shows data only to its allowed audience in 100% of tested cases.
- **SC-003**: An admin override overwrites/loses the user's underlying preference in 0% of cases; removing
  an override auto-restores the original preference in 100% of cases.
- **SC-004**: Historized/private data becomes public via classification/theme/default/aggregate in 0% of
  cases.
- **SC-005**: Exports include the requester's data and exclude other users' private data and secrets in
  100% of cases.
- **SC-006**: At final deletion, personal data is deleted/anonymized in 100% of cases, Coins destroyed via
  a recorded transaction in 100% of cases, and the user is re-identifiable in 0% of cases.
- **SC-007**: Historical/transaction integrity is preserved at deletion in 100% of cases; integrity-
  necessary records are deleted by retention cleanup in 0% of cases.
- **SC-008**: Disconnecting a service auto-erases historized portal data in 0% of cases; reconciling an
  external deletion destroys unrelated portal-native data in 0% of cases.
- **SC-009**: Aggregate outputs de-anonymize or expose an individual's private data in 0% of cases.
- **SC-010**: 100% of sensitive privacy/data actions (override apply/remove, export, deletion steps,
  purge, retention changes) appear in the append-only audit trail.

## Assumptions

- The account deletion lifecycle surface (pending/grace period, user-facing flow) is shared with Identity
  & Users (002); this spec is the authoritative privacy/data definition it references.
- The economy ledger and Coin destruction transaction are owned by Gamification & Economy (013); this spec
  requires the destruction and integrity preservation.
- The authorization engine is owned by Roles & Permissions (003); privacy composes with it as a separate
  gate.
- Connectors (005) own disconnection/sync mechanics; this spec owns the privacy/data consequences
  (history retained, purge separate).
- Retention durations, grace-period length, and privacy-safe aggregation thresholds are configurable
  administrative policy. (Flagged as OQ-101/OQ-102.)

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation.

- **OQ-100 (Preference change under override / stacking)**: Confirm behavior when a user changes their
  preference while an override is active, and that only one effective override applies (no stacking).
- **OQ-101 (Retention & grace durations)**: Confirm retention windows per data class and the
  pending-deletion grace period (product defaults vs admin policy); aligns with OQ-7 (Identity) and OQ-33
  (Events).
- **OQ-102 (Privacy-safe aggregation thresholds)**: Confirm minimum-sample/anonymization thresholds that
  prevent aggregate de-anonymization; aligns with OQ-82 (Statistics).
- **OQ-103 (External-deletion reconciliation policy)**: Confirm how the portal reconciles when a source
  deletes native data (mirror-delete vs retain-as-historical with provenance), aligning with Connectors
  OQ-23.
- **OQ-104 (Anonymization standard)**: Confirm what "anonymized" guarantees (irreversibility, no
  re-identification via joins) and which records are anonymized vs hard-deleted.

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference) and the project
  Constitution (v1.0.0).
- Composes with: `specs/002-identity-users/spec.md` (deletion lifecycle surface; account states),
  `specs/003-roles-permissions/spec.md` (permission as a separate gate; privacy composition),
  `specs/005-connectors/spec.md` (disconnection/source-of-truth/purge), `specs/007-events-history/spec.md`
  (historized ≠ public; retention; anonymization in history), `specs/013-gamification-economy/spec.md`
  (Coin destruction; ledger integrity), and `specs/020-administration/spec.md` (admin override controls;
  audit surface).
- Depends on / references: `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`,
  `architecture/DATA_MODEL.md`, `architecture/EVENT_MODEL.md`.
- Related specs (not owned here): Statistics (privacy-safe aggregation consumer), Community/Leaderboards
  (visibility consumers), and every domain that stores user data (must honor this engine).
