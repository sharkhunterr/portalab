# Feature Specification: Roles, Permissions & Authorization

**Feature Branch**: `003-roles-permissions`
**Created**: 2026-10-01
**Status**: Draft
**Input**: User description: "Detailed functional specification of the Roles, Permissions & Authorization system."

## Role of This Document

This is a **detailed feature specification** for the Roles, Permissions & Authorization system —
the authorization engine referenced by the Identity & Users spec. It conforms to and refines the
superior reference specification (`specs/001-portal-global-spec/spec.md`), the Identity & Users
spec (`specs/002-identity-users/spec.md`), and the product documentation
(`architecture/PERMISSION_MODEL.md`, `architecture/DATA_MODEL.md`, `product/BUSINESS_RULES.md`,
`product/PRODUCT_BLUEPRINT.md`), under the project Constitution
(`.specify/memory/constitution.md`, v1.0.0).

Scope boundary: this spec owns the **authorization decision model** — roles, permissions, groups,
contextual/scoped permissions, the deny-by-default evaluation, extension-declared permissions, and
the audit of sensitive actions. It defines how privacy preferences and admin visibility policies
**interact with** authorization without owning the privacy/visibility engine (a separate Privacy
spec owns that). The single-Admin account lifecycle and transfer flow are owned by the Identity &
Users spec; this spec enforces the authorization consequences. It chooses no technology and
contains no implementation detail.

**Terminology** (aligned with the global spec, OQ-1): Domain Event = a recorded fact; Campaign =
a themed time-bound operation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Deny-by-default authorization of every action (Priority: P1)

For any action a user (or the AI acting for them) attempts, the system evaluates the user's
effective permissions in the relevant context and allows it only if explicitly permitted;
otherwise it denies.

**Why this priority**: Deny-by-default server-side authorization is the single most important
security guarantee; every other capability relies on it being correct.

**Independent Test**: Attempt a permitted action and a non-permitted action as the same user;
confirm the first succeeds and the second is refused with an authorization error, with the
decision made server-side regardless of what the UI offered.

**Acceptance Scenarios**:

1. **Given** a user without a permission for an action, **When** they attempt it, **Then** it is
   refused by default and no state changes.
2. **Given** a user with a permission for an action in a context, **When** they attempt it in that
   context, **Then** it is allowed.
3. **Given** the UI happens to expose a control the user is not permitted to use, **When** the
   action reaches the server, **Then** the server independently refuses it.
4. **Given** no role grants a permission, **When** any non-Admin user attempts the action, **Then**
   it is refused (no implicit grants).

### User Story 2 - Assign roles and groups to users (Priority: P1)

An authorized administrator assigns base and additional roles (and group memberships) to users;
the user's effective permissions are the combination granted by their roles and groups, within
contextual scope.

**Why this priority**: Roles and groups are how permissions are managed at scale; without them,
permissioning is unmanageable and inconsistent.

**Independent Test**: Assign a role and a group to a user; confirm the union of their granted
permissions becomes effective; remove them and confirm the permissions are withdrawn.

**Acceptance Scenarios**:

1. **Given** the base roles (User, Support, Moderator, Editor) and groups, **When** roles/groups
   are assigned to a user, **Then** the user's effective permissions become the union of all
   granted permissions, evaluated within context.
2. **Given** a user with a role removed, **When** evaluated afterward, **Then** permissions granted
   only by that role are no longer effective.
3. **Given** conflicting grants, **When** permissions are evaluated, **Then** an explicit deny
   takes precedence over a grant and the result is deterministic.
4. **Given** any role assignment or group change, **When** it occurs, **Then** a
   `permission.role_assigned` / `permission.group_changed` event and an audit entry are recorded.

### User Story 3 - The single-Admin authorization guarantee (Priority: P1)

The system enforces that exactly one account effectively holds Admin authority, that no other role
can escalate to Admin, and that Admin cannot be temporarily delegated.

**Why this priority**: This is a locked product decision with severe security implications; the
authorization engine must make Admin escalation impossible except via the explicit transfer owned
by Identity & Users.

**Independent Test**: Attempt to grant Admin to a second account, to construct a non-Admin role
that aggregates Admin-equivalent permissions, and to temporarily delegate Admin; confirm all are
refused.

**Acceptance Scenarios**:

1. **Given** one Admin exists, **When** any attempt grants Admin authority to a second account
   outside the explicit transfer flow, **Then** it is refused.
2. **Given** a non-Admin role or group, **When** an attempt adds Admin-only permissions to it,
   **Then** it is refused (Admin-only permissions cannot be delegated into other roles).
3. **Given** the Admin role, **When** temporary or time-boxed delegation is attempted, **Then** it
   is refused and audited.
4. **Given** the AI acting for the Admin, **When** it attempts an action, **Then** it is still
   bounded by the Admin's effective permissions and cannot exceed them.

### User Story 4 - Contextual and scoped permissions (Priority: P2)

Permissions are evaluated within context (self, owned object, module, service, plugin,
community-wide) so that a permission granted in one scope does not leak into another.

**Why this priority**: Scope is what makes permissions safe and precise; without it, a grant
intended for one object or service would apply everywhere.

**Independent Test**: Grant a permission scoped to a specific service (or to "self"); confirm it
applies only within that scope and is denied outside it.

**Acceptance Scenarios**:

1. **Given** a permission scoped to a specific service, **When** the user acts on a different
   service, **Then** it is denied.
2. **Given** a self-scoped permission (e.g., manage own profile), **When** the user acts on another
   user, **Then** it is denied unless a broader scope grants it.
3. **Given** a permission granted at module scope, **When** evaluated for an object in another
   module, **Then** it does not apply.

### User Story 5 - Read vs write/publish/delete separation (Priority: P2)

The system distinguishes read permissions from create, modify, publish, and delete permissions so
that visibility of content is independent from the ability to change or remove it.

**Why this priority**: Content domains (News, Wiki, community, etc.) need the editor/publisher
distinction; conflating read and write would over- or under-grant.

**Independent Test**: Grant read-only on a content type and confirm the user can view but not
create/modify/publish/delete; grant create+modify without publish and confirm drafts can be edited
but not published.

**Acceptance Scenarios**:

1. **Given** read-only permission on a content type, **When** the user attempts to modify or
   publish it, **Then** it is refused.
2. **Given** create and modify but not publish, **When** the user attempts to publish, **Then** it
   is refused while creating/editing a draft succeeds.
3. **Given** delete permission, **When** the user deletes an object, **Then** it is allowed, treated
   as sensitive, confirmed where appropriate, and audited.

### User Story 6 - Extension-declared permissions (plugins & services) (Priority: P2)

Plugins and services (connectors) declare their own permissions, which integrate into the same
model and are evaluated by the same deny-by-default engine; disabling an extension withdraws its
permissions without deleting data.

**Why this priority**: Extensibility is foundational; extension permissions must not be a parallel
mechanism or a bypass.

**Independent Test**: Install a plugin that declares a permission; grant it; confirm it is
evaluated like core permissions; disable the plugin and confirm the permission stops granting
access while its data persists.

**Acceptance Scenarios**:

1. **Given** a plugin declaring a permission, **When** it is installed, **Then** the permission is
   registered in the same model and is deny-by-default until explicitly granted.
2. **Given** a granted plugin permission, **When** the plugin is disabled, **Then** the permission
   no longer grants access and the plugin's data is not deleted.
3. **Given** a plugin-declared permission, **When** it would exceed the granting user's own rights
   or imply Admin authority, **Then** it is refused.

### User Story 7 - Infrastructure, AI, Marketplace, gamification, support, statistics domains (Priority: P2)

Each functional domain exposes its own permissions (infrastructure/service supervision, AI usage,
Marketplace management, gamification/economy management, support, statistics) so that sensitive
capabilities are grantable and auditable independently.

**Why this priority**: These domains include the most sensitive operations (economy changes,
destructive service actions, AI actions); they must be individually controllable.

**Independent Test**: For each domain, grant a representative permission and confirm the domain
action is allowed; revoke it and confirm denial; confirm sensitive ones are audited.

**Acceptance Scenarios**:

1. **Given** `infrastructure.read` but not `services.manage`, **When** the user attempts a
   destructive service action, **Then** it is refused while viewing infrastructure is allowed.
2. **Given** `economy.manage`, **When** the user changes an economy rule, **Then** it is allowed,
   treated as sensitive, and audited; **Given** its absence, **Then** it is refused.
3. **Given** `ai.use`, **When** the user invokes the AI, **Then** the AI acts only within that
   user's other effective permissions and cannot exceed them.

### User Story 8 - Permissions coexist with privacy preferences and admin visibility policy (Priority: P1)

Having permission to read does not override another user's privacy preference, and administrative
visibility policies can constrain what is shown even to otherwise-permitted viewers; the two
systems compose predictably.

**Why this priority**: "Permissions do not replace privacy" and "admin policy may impose
visibility" are locked rules; mishandling them would leak private data.

**Independent Test**: As a user with broad read permission, attempt to view another user's
Private data and confirm it is not shown; apply an admin visibility policy and confirm it
constrains display even for permitted viewers.

**Acceptance Scenarios**:

1. **Given** a viewer with read permission, **When** the target data's visibility is Private,
   **Then** permission alone does not make it visible (privacy preference is honored).
2. **Given** an administrative visibility policy that restricts a field, **When** an otherwise
   permitted viewer requests it, **Then** the policy constrains the display.
3. **Given** the priority order (Security/Permissions > Data Integrity > Privacy > Business Rules >
   Admin Config > User Preferences > Presentation), **When** permission and privacy both apply,
   **Then** authorization gates access first and privacy further restricts what is shown; neither
   silently overrides the other.

### Edge Cases

- **Privilege escalation via aggregation**: No combination of non-Admin roles/groups/plugin
  permissions can sum to Admin-only authority; such grants are refused.
- **Orphaned grant after role/plugin removal**: Removing a role or disabling a plugin immediately
  withdraws its granted permissions at the next evaluation; no stale grant persists.
- **Conflicting grant and deny**: An explicit deny always beats a grant; evaluation is
  deterministic and order-independent.
- **AI exceeding user rights**: Any AI-initiated action that would exceed the current user's
  effective permissions is refused exactly as a human attempt would be.
- **Permission without privacy clearance**: A viewer permitted to read a class of data still cannot
  see another user's Private items; privacy is a separate, non-overridable gate.
- **Admin-policy vs user preference**: An admin visibility policy may restrict display; it does not
  erase the user's underlying preference (restoration is owned by Privacy/Identity specs).
- **Scope mismatch**: A permission granted in one scope (service A, module X, self) never applies in
  another scope.
- **Self-service limits**: A user's self-scoped permissions never allow acting on other users or on
  global configuration.
- **Sensitive action without confirmation**: A sensitive action that requires confirmation and
  receives none is not performed.
- **Unauthorized surface**: When access is denied, the surface shows a distinguishable
  "unauthorized" state rather than a dead-end or a silent empty result, and does not leak the
  existence of data the user may not know about where that itself is sensitive.
- **Deleting/demoting the sole Admin**: Refused by this engine unless the Identity & Users transfer
  flow has first ensured exactly one Admin remains.
- **Plugin declaring a reserved/Admin-only permission**: Refused at registration; plugins cannot
  introduce Admin-equivalent authority.

## Requirements *(mandatory)*

### Functional Requirements

#### Authorization Model & Evaluation
- **FR-001**: The system MUST evaluate authorization server-side for every non-public action using
  deny-by-default: access is refused unless an effective permission explicitly grants it.
- **FR-002**: The system MUST compute a user's effective permissions as the union of permissions
  granted by their roles and group memberships, then apply scope and any explicit denies.
- **FR-003**: An explicit deny MUST take precedence over any grant, and evaluation MUST be
  deterministic and independent of grant order.
- **FR-004**: Permissions MUST be expressed in a `domain.action.scope` form and MUST be evaluated
  within the relevant context (self, owned object, module, service, plugin, community-wide).
- **FR-005**: The UI MUST NOT be the authorization boundary; any action reaching the server MUST be
  independently authorized regardless of what the client exposed.

#### Roles & Groups
- **FR-006**: The system MUST provide base roles (User, Support, Moderator, Editor, Admin) and MUST
  allow users to hold the base User role plus any combination of non-Admin roles.
- **FR-007**: The system MUST support groups whose membership grants the group's permissions to
  member users within context.
- **FR-008**: Role and group definitions MUST map to permissions, and changing a user's roles or
  group memberships MUST be a sensitive, audited operation.

#### Single-Admin Guarantee (authorization consequences)
- **FR-009**: The system MUST ensure exactly one account effectively holds Admin authority and MUST
  refuse any grant that would create a second Admin outside the Identity & Users transfer flow.
- **FR-010**: Admin-only permissions MUST NOT be assignable to non-Admin roles, groups, plugins, or
  services (no escalation by aggregation).
- **FR-011**: The system MUST refuse any temporary or time-boxed delegation of the Admin role, and
  MUST audit the attempt.
- **FR-012**: The system MUST refuse an authorization that would leave zero Admins; reduction/removal
  of the sole Admin is only valid as part of the explicit transfer that preserves exactly one Admin.

#### Contextual & Scoped Permissions
- **FR-013**: A permission granted in one scope MUST NOT apply in a different scope.
- **FR-014**: Self-scoped permissions MUST allow a user to act only on their own objects and MUST
  NOT allow acting on other users or global configuration.
- **FR-015**: Object/owner-scoped permissions MUST evaluate ownership/relationship in context.

#### Read vs Create/Modify/Publish/Delete
- **FR-016**: The system MUST distinguish read permissions from create, modify, publish, and delete
  permissions as separately grantable capabilities.
- **FR-017**: Read permission MUST NOT imply any write capability, and create/modify MUST NOT imply
  publish.
- **FR-018**: Delete and publish MUST be treatable as sensitive actions subject to confirmation
  where appropriate and MUST be audited.

#### Administration
- **FR-019**: Administrative management of roles, groups, permissions, and policies MUST itself be
  permission-gated and MUST be sensitive and audited.
- **FR-020**: The system MUST expose administration permissions covering the domains enumerated by
  the product (users, modules/plugins, connectors/services, content, support, gamification,
  Marketplace, statistics, notifications, AI, appearance, security, audit, automations, portal
  health).

#### Extension-Declared Permissions (Plugins & Services)
- **FR-021**: Plugins and services MUST be able to declare permissions that register into the same
  model and are evaluated by the same deny-by-default engine.
- **FR-022**: Extension-declared permissions MUST default to denied until explicitly granted, MUST
  NOT exceed the granting user's own rights, and MUST NOT introduce Admin-equivalent authority.
- **FR-023**: Disabling a plugin or disconnecting a service MUST withdraw its permissions at the
  next evaluation without deleting the extension's data.

#### Domain Permissions
- **FR-024**: The system MUST expose service/infrastructure permissions distinguishing read
  (`services.read`, `infrastructure.read`) from management/destructive actions (`services.manage`),
  with destructive service/data actions treated as sensitive and audited.
- **FR-025**: The system MUST expose an AI-usage permission (`ai.use`); the AI MUST act only within
  the invoking user's other effective permissions and MUST NEVER exceed them or bypass a check.
- **FR-026**: The system MUST expose Marketplace permissions (`marketplace.manage`) and economy
  permissions (`economy.manage`); economy-rule changes and significant refunds MUST be sensitive and
  audited.
- **FR-027**: The system MUST expose gamification permissions governing reward rules, campaigns, and
  manual rewards; manual rewards and rule changes MUST be sensitive and audited.
- **FR-028**: The system MUST expose support permissions (e.g., `tickets.create`, `tickets.manage`,
  `wiki.edit`, `news.publish`) consistent with the read/write/publish separation.
- **FR-029**: The system MUST expose statistics permissions governing access to and management of
  statistics, including unlockable and cross-service statistics, within privacy constraints.
- **FR-030**: The system MUST expose events/automation permissions (`events.manage`,
  `automation.manage`); automations MUST execute only within their author's effective permissions.

#### Interaction with Privacy & Admin Visibility Policy
- **FR-031**: Read permission MUST NOT override another user's privacy preference; privacy is a
  separate gate that further restricts what an otherwise-permitted viewer may see.
- **FR-032**: Administrative visibility policies MUST be able to constrain what is displayed even to
  permitted viewers, following the product priority order (Security/Permissions > Data Integrity >
  Privacy > Business Rules > Admin Config > User Preferences > Presentation).
- **FR-033**: The authorization engine MUST NOT alter or erase a user's stored privacy preference;
  it only gates access and composes with the privacy/visibility engine.

#### Audit of Sensitive Actions
- **FR-034**: The system MUST classify as sensitive at least: deletions, permission/role/group
  changes, Admin-transfer attempts, significant refunds, economy-rule changes, destructive
  service/data actions, visibility-policy changes, and publish actions.
- **FR-035**: Every sensitive action (allowed or refused) MUST produce an audit entry containing
  actor, action, timestamp, context/scope, decision (allow/deny), and result where relevant.
- **FR-036**: Authorization decisions and permission changes MUST emit domain events with
  `occurred_at` distinct from `received_at`; consumers MUST be idempotent where duplicate delivery
  is possible.
- **FR-037**: Audit entries MUST be tamper-evident in intent (append-only; not rewritten) consistent
  with the Observability & Auditability and Versioning principles.

### Illustrative Permission Catalog

Permissions use the `domain.action.scope` form; scope is contextual. Names are illustrative and
authoritative only as examples of the model (detailed domain specs may refine them):

- **Users/Identity**: `users.read`, `users.manage`, `users.self.manage`, `users.roles.manage`,
  `users.admin.transfer` (sensitive, Admin-only).
- **Content (read/write/publish/delete)**: `news.read`/`news.create`/`news.modify`/`news.publish`/
  `news.delete`; `wiki.read`/`wiki.edit`/`wiki.publish`/`wiki.delete`.
- **Services/Infrastructure**: `services.read`, `services.manage`, `infrastructure.read`.
- **AI**: `ai.use`.
- **Marketplace/Economy**: `marketplace.manage`, `economy.manage`.
- **Gamification**: `gamification.manage`, `rewards.grant` (manual, sensitive), `campaigns.manage`.
- **Support**: `tickets.create`, `tickets.manage`, `incidents.manage`, `feedback.read`.
- **Statistics**: `statistics.read`, `statistics.manage`.
- **Events/Automation**: `events.manage`, `automation.manage`.
- **Security/Audit**: `security.manage`, `audit.read`.

Reserved: Admin-only permissions form a reserved set that cannot be assigned to non-Admin roles,
groups, plugins, or services.

### Permission-Related Domain Events

Names illustrative; each carries actor/context, subject reference, metadata, and version.

- `permission.role_assigned`
- `permission.role_revoked`
- `permission.group_changed`
- `permission.permission_granted`
- `permission.permission_revoked`
- `permission.policy_changed`
- `permission.admin_transfer_attempted`
- `permission.denied` (notable/sensitive denials, for audit)

### Key Entities

- **Permission**: A grantable capability named `domain.action.scope`; may be core or
  extension-declared; may be reserved (Admin-only).
- **Role**: A named set of permissions; base roles are User, Support, Moderator, Editor, Admin
  (Admin is singular and non-delegable; its lifecycle is owned by Identity & Users).
- **Group**: A named collection of users whose membership grants the group's permissions in context.
- **Grant**: An association (role→permissions, group→permissions, user→role/group) producing
  effective permissions.
- **Scope/Context**: The evaluation context (self, owned object, module, service, plugin,
  community-wide) in which a permission applies.
- **Authorization Decision**: The deny-by-default evaluation outcome (allow/deny) for an action in a
  context, with reason.
- **Policy (referenced)**: Administrative visibility/constraint policy that composes with
  authorization; the visibility engine is owned by the Privacy spec.
- **AuditEntry**: Append-only record of a sensitive action (actor, action, timestamp, context,
  decision, result).
- **Domain Event**: A permission/authorization recorded fact (see Events).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of non-public actions are authorized server-side; 0% rely solely on UI gating.
- **SC-002**: 100% of actions lacking an explicit granting permission are denied by default.
- **SC-003**: The portal maintains exactly one effective Admin in 100% of states; 100% of attempts
  to create a second Admin, escalate via aggregation, or temporarily delegate Admin are refused.
- **SC-004**: 100% of AI-initiated actions that exceed the invoking user's effective permissions are
  refused (the AI never exceeds the user).
- **SC-005**: Granting read permission results in 0 cases of another user's Private data becoming
  visible solely due to that permission.
- **SC-006**: An administrative visibility policy constrains display for permitted viewers in 100%
  of applicable cases, while 0 user privacy preferences are erased by the authorization engine.
- **SC-007**: A permission scoped to one scope applies in 0% of other scopes.
- **SC-008**: Read-only grants permit write/publish/delete in 0% of attempts.
- **SC-009**: Disabling a plugin or disconnecting a service withdraws its permissions in 100% of
  subsequent evaluations, with 0 data deletions caused by the withdrawal.
- **SC-010**: 100% of sensitive actions (allowed or refused) produce an audit entry with actor,
  action, timestamp, context, decision, and result where relevant; 0 audit entries are rewritten.

## Assumptions

- The base role catalog (User, Support, Moderator, Editor, Admin) comes from the Permission Model;
  additional non-Admin roles/groups may be defined administratively without changing these rules.
- The concrete representation of permissions, scopes, and evaluation is an implementation/plan
  decision; this spec fixes only the model's behavior and guarantees.
- The privacy/visibility engine (how visibility levels and admin overrides are stored and restored)
  is owned by a separate Privacy spec; this spec composes with it per the priority order.
- "Sensitive action" is at least the enumerated set (FR-034); detailed specs may mark additional
  actions sensitive but may not remove these.
- Whether end users (non-Admin) may define custom roles/groups, or only the Admin may, is treated as
  administrative policy. (Flagged as OQ-11.)

## Open Questions & Flagged Ambiguities

Flagged rather than invented, per instruction. To be resolved via `/speckit.clarify` or a product
decision before implementation.

- **OQ-11 (Custom role/group authorship)**: Confirm who may create custom roles and groups (Admin
  only, or delegated to certain roles) and whether custom roles may bundle arbitrary non-reserved
  permissions.
- **OQ-12 (Group semantics vs roles)**: Confirm whether groups are purely permission-bearing, or
  also carry community/visibility meaning (e.g., Leaderboard groups), to avoid overloading the
  concept.
- **OQ-13 (Deny modeling)**: Confirm whether explicit per-user/per-group denies are a product
  feature or whether denial is solely the absence of a grant (this spec supports explicit deny as
  the safe default; confirm scope of use).
- **OQ-14 (Notable-denial auditing threshold)**: Confirm which denials are "notable" enough to audit
  (all sensitive-action denials vs all denials) to balance auditability against noise.
- **OQ-15 (Infrastructure permission granularity)**: Confirm whether infrastructure supervision is a
  single `infrastructure.read` or finer-grained per-metric/per-operation permissions.

## Dependencies

- Conforms to: `specs/001-portal-global-spec/spec.md` (superior reference),
  `specs/002-identity-users/spec.md` (Admin lifecycle/transfer, user roles), and the project
  Constitution (v1.0.0).
- Depends on / references: `architecture/PERMISSION_MODEL.md`, `architecture/DATA_MODEL.md`,
  `architecture/EVENT_MODEL.md`, `product/BUSINESS_RULES.md`, `product/PRODUCT_BLUEPRINT.md`.
- Related specs (not owned here): the Privacy spec (021) (visibility engine and admin overrides); each
  functional domain's detailed spec (Services, AI, Marketplace, Gamification, Support, Statistics,
  Automations) refines its own permissions within this model.
