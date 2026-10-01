# Feature Specification: Identity & Users

**Feature Branch**: `002-identity-users`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Detailed functional specification of the Identity & Users domain."

## Role of This Document

This is a **detailed feature specification** for the Identity & Users domain. It conforms to and
refines the superior reference specification (`specs/001-portal-global-spec/spec.md`) and the
product documentation (`product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`,
`architecture/PERMISSION_MODEL.md`, `architecture/DATA_MODEL.md`, `ux/UX_PRINCIPLES.md`), under
the project Constitution (`.specify/memory/constitution.md`, v1.0.0).

Scope boundary: this spec defines user identity, accounts, profile, preferences, onboarding, the
personal-data lifecycle (export/deletion/anonymization), and user-related events/audit. It
references Roles & Permissions as they relate to users but does not fully specify the
authorization engine (a separate Permissions spec owns that). It chooses no technology and
contains no implementation detail.

**Terminology** (aligned with the global spec, OQ-1): Domain Event = a recorded fact; Campaign =
a themed time-bound operation. User-related facts below are Domain Events.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create an account and complete onboarding (Priority: P1)

A prospective user creates an account, verifies their identity enough to sign in, and is guided
through onboarding (profile, interests, notification and privacy choices) to an automatically
configured starter environment.

**Why this priority**: Without account creation and a working first-run, there are no users and
no portal. It is the entry gate to every other capability.

**Independent Test**: Register a brand-new account; complete onboarding; confirm the account is
Active, a display name and default preferences exist, privacy defaults are applied, and a starter
dashboard is configured, with no dead-ends.

**Acceptance Scenarios**:

1. **Given** no account exists for an identifier, **When** a user registers with required
   credentials and a unique display name, **Then** an account is created in Pending Verification
   state and a `user.created` event is recorded.
2. **Given** a newly created account, **When** identity verification succeeds, **Then** the account
   becomes Active and onboarding begins.
3. **Given** onboarding, **When** the user sets profile, interests, notification and privacy
   preferences, **Then** those preferences are persisted and honored immediately, and a starter
   dashboard is configured within administrative policy.
4. **Given** a display name already taken by another user, **When** registration is attempted with
   it, **Then** registration is rejected with an actionable message.

### User Story 2 - Authenticate and manage a session (Priority: P1)

An existing active user signs in, and the portal establishes an authenticated session under the
user's effective permissions; sign-out ends the session.

**Why this priority**: Authentication is the precondition for all authorized behavior; the AI and
every module operate under the authenticated user's permissions.

**Independent Test**: Sign in with valid credentials for an Active account and confirm access to
permitted areas; sign in with invalid credentials and confirm denial; sign out and confirm the
session no longer grants access.

**Acceptance Scenarios**:

1. **Given** an Active account, **When** the user authenticates with valid credentials, **Then** an
   authenticated session is established and a `user.signed_in` event is recorded.
2. **Given** invalid credentials, **When** authentication is attempted, **Then** access is denied
   with an actionable, non-enumerating message and a failed attempt is recorded for audit.
3. **Given** an account that is not Active (Pending Verification, Suspended, Pending Deletion, or
   Deleted), **When** the user attempts to authenticate, **Then** sign-in is refused with a
   state-appropriate message.
4. **Given** an authenticated session, **When** the user signs out, **Then** the session is ended
   and a `user.signed_out` event is recorded.

### User Story 3 - View and edit profile, avatar, and display name (Priority: P2)

A user views and edits their profile: display name, avatar, and profile fields, each with its own
visibility, without affecting functional permissions.

**Why this priority**: Profile and identity presentation are core to the community experience and
to the "one coherent environment" promise, but subordinate to account existence and auth.

**Independent Test**: Edit display name, upload/replace/remove avatar, and change a profile field's
visibility; confirm changes persist, respect uniqueness/validation, and that visibility is
independent of permissions.

**Acceptance Scenarios**:

1. **Given** an Active user, **When** they change their display name to an available value, **Then**
   the new name is persisted and a `user.profile_updated` event is recorded.
2. **Given** an Active user, **When** they upload an avatar that meets validation rules, **Then** it
   replaces any previous avatar and the previous one is no longer referenced.
3. **Given** a profile field, **When** the user sets its visibility to Private, **Then** it is not
   shown to other audiences and does not become public automatically under any theme or default.
4. **Given** a display name change to a value already in use, **When** saved, **Then** it is rejected
   with an actionable message.

### User Story 4 - Manage preferences (Priority: P2)

A user manages preferences (locale, notification categories, privacy/visibility defaults,
accessibility, theme) within administrative policy, and the portal honors them.

**Why this priority**: Preferences are the user-level tier of the configuration hierarchy and govern
personalization, notifications, and accessibility.

**Independent Test**: Change notification categories, a visibility default, and an accessibility
preference; confirm each is honored and retained where still permitted by policy.

**Acceptance Scenarios**:

1. **Given** a user preference permitted by policy, **When** the user changes it, **Then** it is
   persisted and honored, and a `user.preferences_updated` event is recorded.
2. **Given** an administrative policy that constrains a preference, **When** the user's stored
   preference conflicts, **Then** policy takes precedence while the user's underlying preference is
   retained for restoration if the policy is later relaxed.
3. **Given** an accessibility preference (e.g., reduced motion), **When** set, **Then** it takes
   precedence over purely visual theme effects.

### User Story 5 - Export personal data (Priority: P2)

A user requests an export of their personal data and receives a complete, inspectable copy of the
data the portal holds about them.

**Why this priority**: Data export is a locked privacy capability and a prerequisite for informed
deletion.

**Independent Test**: Request an export as an Active user; confirm the export is produced, contains
the user's personal data and a representation of their history, and that a `user.data_exported`
event and audit entry are recorded.

**Acceptance Scenarios**:

1. **Given** an Active user, **When** they request a data export, **Then** an export is produced
   covering their personal data and historized representations attributable to them, and a
   `user.data_export_requested` then `user.data_exported` event is recorded.
2. **Given** an export request, **When** it completes, **Then** the content excludes other users'
   private data and secrets.

### User Story 6 - Delete account: pending deletion, anonymization, final deletion (Priority: P1)

A user requests account deletion. The account enters Pending Deletion for a grace period; the user
may cancel. At final deletion, personal data is deleted or anonymized, remaining Coins are
destroyed, and integrity-necessary history is retained in anonymized/aggregate form.

**Why this priority**: The deletion lifecycle encodes several locked rules (Coins destroyed,
integrity history preserved/anonymized, private data never auto-public) with legal and trust
weight; getting it wrong is high-impact and hard to reverse.

**Independent Test**: Request deletion and confirm Pending Deletion with a cancel option; cancel and
confirm restoration to the prior state; separately, let deletion finalize and confirm personal data
removed/anonymized, Coins destroyed, transaction/history integrity preserved, and the user no longer
identifiable.

**Acceptance Scenarios**:

1. **Given** an Active user, **When** they confirm a deletion request, **Then** the account enters
   Pending Deletion, sign-in and activity are restricted per policy, and a `user.deletion_requested`
   event plus an audit entry are recorded.
2. **Given** an account in Pending Deletion within the grace period, **When** the user (or Admin)
   cancels, **Then** the account is restored to its prior active/suspended state and a
   `user.deletion_cancelled` event is recorded.
3. **Given** an account in Pending Deletion past the grace period, **When** final deletion runs,
   **Then** personal data is deleted or anonymized, any remaining Coins are destroyed via a recorded
   economy transaction, display name is released or anonymized, and a `user.anonymized` (if
   applicable) and `user.deleted` event plus audit entries are recorded.
4. **Given** final deletion, **When** it completes, **Then** historical transactions and
   integrity-necessary history remain but are no longer attributable to an identifiable person, and
   no private data of the user is made public as a result.

### User Story 7 - Account activity state: active, inactive, suspended (Priority: P2)

The system reflects whether an account is active, inactive (dormant), or suspended, and uses this
state in authentication, community eligibility, and visibility, without deleting data.

**Why this priority**: "Active account" gates capabilities such as voting; distinguishing
inactive/suspended from deleted prevents data loss and clarifies eligibility.

**Independent Test**: Mark an account inactive after a dormancy condition and confirm it is excluded
from "active account" eligibility while its data persists; suspend an account (Admin) and confirm
sign-in refusal; reactivate and confirm restoration.

**Acceptance Scenarios**:

1. **Given** an Active account meeting a dormancy condition, **When** it is marked Inactive, **Then**
   its data is preserved and a `user.deactivated` event is recorded; it is excluded from "active
   account" eligibility (e.g., voting) until it becomes Active again.
2. **Given** an Admin suspends an account, **When** the user attempts to sign in, **Then** sign-in is
   refused and a `user.suspended` event plus audit entry are recorded.
3. **Given** a Suspended or Inactive account, **When** it is reactivated by the appropriate actor,
   **Then** it returns to Active and a `user.reactivated` event is recorded.

### User Story 8 - Roles and the single-Admin guarantee (Priority: P1)

Users may hold roles (User, Support, Moderator, Editor) in addition to the base User role; exactly
one account holds Admin, and the Admin role cannot be temporarily delegated.

**Why this priority**: The single-Admin, no-delegation rule is a locked decision that this domain
must enforce at the account level.

**Independent Test**: Assign non-Admin roles to users and confirm they take effect; attempt to create
a second Admin or temporarily delegate Admin and confirm both are refused; attempt to delete the sole
Admin and confirm it is refused or requires explicit Admin transfer.

**Acceptance Scenarios**:

1. **Given** the portal, **When** roles are assigned to a user, **Then** a user may hold any
   combination of non-Admin roles and a `user.role_changed` event plus audit entry are recorded.
2. **Given** exactly one Admin exists, **When** an attempt is made to grant Admin to a second account,
   **Then** it is refused unless performed as an explicit Admin transfer that leaves exactly one Admin.
3. **Given** the Admin role, **When** temporary delegation is attempted, **Then** it is refused.
4. **Given** the sole Admin account, **When** deletion or role removal is attempted, **Then** it is
   refused unless Admin is first transferred so that exactly one Admin remains.

### Edge Cases

- **Duplicate display name / identifier**: Registration or rename with a taken value is rejected;
  identifiers are unique.
- **Auth on non-active states**: Sign-in is refused for Pending Verification, Suspended, Pending
  Deletion, and Deleted, each with a state-appropriate (non-enumerating) message.
- **Cancel deletion after grace period**: Once final deletion has run, it cannot be cancelled;
  cancellation is only possible within the grace period.
- **Deleting the sole Admin**: Refused unless Admin is transferred first; the system never ends up
  with zero Admins or two Admins.
- **Coins at final deletion**: Remaining Coins are destroyed via a recorded transaction; no refund
  to real value exists (Coins are virtual-only).
- **History attribution after anonymization**: History/transactions required for integrity remain
  but reference an anonymized subject; they are never made public as a side effect.
- **Private profile data under themes/defaults**: Visibility set to Private is never overridden to
  public by a theme change or a new default.
- **Avatar replacement/removal**: Replacing or removing an avatar leaves no publicly dangling
  reference to the prior image.
- **Re-registration after deletion**: A released display name/identifier may be reusable per policy,
  but the new account is a distinct identity with no access to the deleted user's history.
- **Admin-initiated vs user-initiated deletion**: Both follow the same lifecycle; Admin actions are
  additionally audited as administrative.
- **Concurrent sessions**: Sign-out or suspension takes effect for the session; policy governs
  whether other active sessions are also ended.
- **Pending Verification never completed**: An account that never verifies within policy may be
  expired/removed via the deletion lifecycle, not silently orphaned.

## Requirements *(mandatory)*

### Functional Requirements

#### Identity & Accounts
- **FR-001**: The system MUST represent each user as a distinct identity with a unique identifier and
  a unique display name.
- **FR-002**: The system MUST support account creation requiring the minimum credentials needed to
  authenticate and a unique display name.
- **FR-003**: The system MUST model an explicit account lifecycle state: Pending Verification, Active,
  Inactive, Suspended, Pending Deletion, Deleted (terminal).
- **FR-004**: The system MUST distinguish "active account" (eligible for capabilities such as voting)
  from Inactive/Suspended/Pending Deletion/Deleted accounts.

#### Authentication & Session
- **FR-005**: The system MUST authenticate users before granting any non-public access, enforced
  server-side with default-deny.
- **FR-006**: The system MUST refuse authentication for accounts not in Active state, with a
  state-appropriate message that does not enable account enumeration.
- **FR-007**: The system MUST establish a session scoped to the user's effective permissions and MUST
  allow the user to sign out, ending that session.
- **FR-008**: The system MUST record failed authentication attempts for audit without exposing whether
  an identifier exists.

#### Profile, Avatar, Display Name
- **FR-009**: Users MUST be able to view and edit their profile, including display name and avatar.
- **FR-010**: Display name changes MUST enforce uniqueness and validation and MUST be rejected with an
  actionable message on conflict.
- **FR-011**: Avatar upload/replace/remove MUST enforce validation and MUST leave no publicly
  accessible dangling reference to a replaced/removed image.
- **FR-012**: Each profile field MUST carry a visibility (Public, Community, Leaderboard-only, Private)
  independent of functional permissions; Private data MUST NEVER become public automatically.

#### Preferences
- **FR-013**: Users MUST be able to manage preferences including locale, notification categories,
  visibility defaults, accessibility, and theme, within administrative policy.
- **FR-014**: Preferences MUST follow the configuration hierarchy (Global, Module, Plugin, User); when
  policy constrains a preference, policy MUST take precedence while the user's underlying preference is
  retained for later restoration.
- **FR-015**: Accessibility preferences MUST take precedence over purely visual theme effects.

#### Onboarding
- **FR-016**: Onboarding MUST guide profile, interests, notification, and privacy choices and MUST
  result in applied privacy defaults and an automatically configured starter dashboard within policy,
  with no dead-ends.
- **FR-017**: Preferences set during onboarding MUST be honored immediately upon completion.

#### Personal Data & Export
- **FR-018**: Users MUST be able to inspect the personal data the portal holds about them.
- **FR-019**: Users MUST be able to request an export covering their personal data and historized
  representations attributable to them; the export MUST exclude other users' private data and any
  secrets.

#### Deletion Lifecycle (Pending Deletion, Anonymization, Final Deletion)
- **FR-020**: A deletion request MUST move the account to Pending Deletion for a defined grace period
  during which the user (or Admin) MAY cancel and be restored to the prior state.
- **FR-021**: During Pending Deletion, sign-in and activity MUST be restricted per policy, and the
  account MUST be excluded from "active account" eligibility.
- **FR-022**: At final deletion, the system MUST delete or anonymize personal data such that the user
  is no longer identifiable.
- **FR-023**: At final deletion, any remaining Coins MUST be destroyed via a recorded economy
  transaction (Coins are virtual-only; no real-value refund).
- **FR-024**: At final deletion, history and transactions necessary for integrity MUST be retained but
  MUST reference an anonymized subject; retention MUST NOT make previously private data public.
- **FR-025**: Final deletion MUST be irreversible; cancellation MUST only be possible within the grace
  period before final deletion.
- **FR-026**: The display name/identifier of a deleted account MUST be released or anonymized per
  policy; any reuse creates a distinct identity with no access to the deleted user's history.

#### Roles & Permissions (relations)
- **FR-027**: A user MUST be able to hold the base User role plus any combination of non-Admin roles
  (Support, Moderator, Editor); role assignment MUST be audited.
- **FR-028**: The system MUST guarantee exactly one Admin account at all times and MUST refuse creation
  of a second Admin except via an explicit Admin transfer that leaves exactly one Admin.
- **FR-029**: The system MUST refuse temporary delegation of the Admin role.
- **FR-030**: The system MUST refuse deletion or Admin-role removal of the sole Admin unless Admin is
  first transferred so that exactly one Admin remains (never zero, never two).
- **FR-031**: Changing a user's roles/permissions is a sensitive operation and MUST be confirmed where
  appropriate and audited.

#### Account Activity State Transitions
- **FR-032**: The system MUST support marking an account Inactive on a dormancy condition without
  deleting data, and reactivating it to Active.
- **FR-033**: An authorized actor MUST be able to Suspend and later reactivate an account; suspension
  MUST refuse sign-in and MUST be audited.

#### User History, Audit & Events
- **FR-034**: The system MUST maintain user history with provenance; user history MUST NOT be treated
  as automatically public.
- **FR-035**: Sensitive user operations (role changes, suspension, deletion steps, Admin transfer, data
  export) MUST produce audit entries containing actor, action, timestamp, context, and result where
  relevant.
- **FR-036**: The system MUST record user-related domain events (see Events) with `occurred_at` distinct
  from `received_at`; consumers MUST be idempotent where duplicate delivery is possible.

### User-Related Domain Events

The domain MUST emit at least the following events (names illustrative, aligned with the Event Model).
Each carries actor/context, subject user reference, metadata, and version.

- `user.created`
- `user.verified`
- `user.signed_in`
- `user.signed_out`
- `user.profile_updated`
- `user.preferences_updated`
- `user.role_changed`
- `user.admin_transferred`
- `user.deactivated` (to Inactive)
- `user.reactivated` (to Active)
- `user.suspended`
- `user.data_export_requested`
- `user.data_exported`
- `user.deletion_requested` (to Pending Deletion)
- `user.deletion_cancelled`
- `user.anonymized`
- `user.deleted` (terminal; aligns with global `user.deleted`)
- `user.level_up` (progression; produced elsewhere but attributable to the user)

### Permissions (relations)

Illustrative permissions in the `domain.action.scope` form (the Permissions spec owns the full model):

- `users.read` — view users/profiles within visibility and policy.
- `users.manage` — administrative management of accounts (suspend, reactivate, role changes).
- `users.self.manage` — a user managing their own profile, preferences, export, and deletion.
- `users.roles.manage` — assign/revoke non-Admin roles; sensitive.
- `users.admin.transfer` — perform the single-Admin transfer; sensitive, Admin-only.

Rules: deny-by-default; a user may always act on themselves via `users.self.manage` within policy;
Admin-only operations never grant a second concurrent Admin; AI acts only within the current user's
effective permissions.

### Account State Model

**States**: Pending Verification, Active, Inactive, Suspended, Pending Deletion, Deleted (terminal).

**Transitions** (actor in parentheses):

- Pending Verification to Active (system, on successful verification)
- Pending Verification to Pending Deletion / Deleted (system/Admin, on verification expiry per policy)
- Active to Inactive (system, on dormancy) ; Inactive to Active (user/system, on return)
- Active/Inactive to Suspended (Admin) ; Suspended to Active (Admin)
- Active/Inactive/Suspended to Pending Deletion (user self-request, or Admin)
- Pending Deletion to prior state (user/Admin cancel within grace period)
- Pending Deletion to Deleted (system, at grace-period end; performs anonymization + Coin destruction)

**Invariants**:
- Exactly one account is Admin at all times (never zero, never two).
- Only Active accounts are "active accounts" for eligibility purposes (e.g., voting).
- Deleted is terminal and irreversible.
- No transition causes previously Private data to become public.

### Key Entities

- **User**: Distinct identity with unique identifier and display name; holds account state, roles,
  preferences, visibility policy, profile, avatar reference, progression, and links to history,
  transactions, purchases, votes, funding.
- **Account State**: The lifecycle state of a User (see State Model).
- **Profile**: Display name, avatar reference, and profile fields, each with a visibility.
- **Preference**: A user-level setting within the configuration hierarchy, retained for restoration when
  overridden by policy.
- **Role / Permission (referenced)**: Named role mapped to permissions; Admin is singular and
  non-delegable (full model owned by the Permissions spec).
- **VisibilityPolicy (referenced)**: Effective visibility, separate from permissions, with
  preserve-and-restore admin override (full model owned by the Privacy spec).
- **Deletion Request**: A record of a requested deletion, its grace-period deadline, requester, and
  cancellation status.
- **HistoryEntry (referenced)**: Persisted user history with provenance; not automatically public.
- **AuditEntry (referenced)**: Record of a sensitive user action (actor, action, timestamp, context,
  result).
- **EconomyTransaction (referenced)**: Includes the Coin-destruction transaction at final deletion.
- **Domain Event**: A user-related recorded fact (see Events).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of new accounts complete onboarding to an Active state with a display name, default
  preferences, applied privacy defaults, and a starter dashboard, with no dead-ends.
- **SC-002**: Authentication is refused in 100% of attempts against non-Active accounts, and no message
  distinguishes "unknown identifier" from "wrong credential" (no account enumeration).
- **SC-003**: Display name and identifier uniqueness is enforced in 100% of registration and rename
  attempts.
- **SC-004**: The portal maintains exactly one Admin in 100% of states; 100% of attempts to create a
  second Admin, delete/demote the sole Admin without transfer, or temporarily delegate Admin are refused.
- **SC-005**: 100% of data-export requests produce a copy that includes the requester's personal data
  and excludes other users' private data and secrets.
- **SC-006**: A deletion request is cancellable in 100% of cases within the grace period and in 0% of
  cases after final deletion.
- **SC-007**: At final deletion, 100% of remaining Coins are destroyed via a recorded transaction, the
  user is no longer identifiable, and 0 previously private data items become public.
- **SC-008**: Integrity-necessary history/transactions are retained in 100% of final deletions while
  referencing an anonymized subject.
- **SC-009**: 100% of sensitive user operations produce an audit entry with actor, action, timestamp,
  context, and result where relevant.
- **SC-010**: Setting a profile field or default to Private results in 0 cases of it becoming public due
  to a theme change or new default.

## Assumptions

- The concrete authentication method (credentials, SSO, multi-factor) is an implementation/plan
  decision; this spec requires only server-side, default-deny authentication with non-enumerating errors.
- The exact grace-period duration for Pending Deletion and the exact dormancy threshold for Inactive are
  configurable administrative policies; this spec requires their existence, not fixed values.
- "Anonymization" means severing identifiability while preserving records required for integrity (e.g.,
  economy transaction ledger, aggregate statistics), consistent with Business Rules.
- The first account provisioned for a fresh portal becomes the single Admin; thereafter Admin moves only
  via explicit transfer. (Flagged as OQ-6 for confirmation.)
- Whether released display names/identifiers are reusable is governed by administrative policy; the
  default assumption is that reuse creates a distinct identity with no inherited history.
- Full visibility/permission engines are specified elsewhere; this spec references them and must not
  contradict them.

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation.

- **OQ-6 (Initial Admin bootstrap)**: The product mandates exactly one Admin but does not state how the
  first Admin is established on a fresh portal. Assumption: the first provisioned account becomes Admin;
  confirm.
- **OQ-7 (Pending-deletion grace period & dormancy threshold)**: Durations are treated as admin policy;
  confirm whether product-level defaults must be fixed here.
- **OQ-8 (Display-name/identifier reuse after deletion)**: Confirm whether released identifiers are
  reusable and under what policy.
- **OQ-9 (Admin self-deletion / transfer flow)**: Confirm the exact required flow for an Admin who wishes
  to delete their own account (mandatory transfer-first vs blocked entirely).
- **OQ-10 (Concurrent session revocation)**: Confirm whether suspension/deletion must immediately revoke
  all of a user's other active sessions.

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference) and the project Constitution
  (v1.0.0).
- Depends on / references: `product/PRODUCT_BLUEPRINT.md`, `product/BUSINESS_RULES.md`,
  `architecture/PERMISSION_MODEL.md`, `architecture/DATA_MODEL.md`, `architecture/EVENT_MODEL.md`,
  `ux/UX_PRINCIPLES.md`.
- Related specs (not owned here): a Roles & Permissions spec (authorization engine), the Privacy spec (021)
  (visibility engine and admin overrides), and a Notifications spec (category delivery).

