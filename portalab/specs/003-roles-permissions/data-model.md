# Data Model — Authorization & minimal Audit

Schemas `authz` and `audit` (conventions per 001). FKs only intra-schema or to `identity.users(id)`.

## authz.permissions
`key` text pk (`domain.action[.scope-kind]`) · `description` · `declared_by` (`core|module:<name>|plugin:<id>`) · `sensitive` bool · `reserved` bool (Admin-only) · `requires_confirmation` bool · `enabled` bool · `created_at`. Upserted at startup from declarations; `enabled=false` when the declaring plugin is disabled.

## authz.roles
`id` · `key` unique (`user|support|moderator|editor|admin|custom:*`) · `name` · `kind` (`base|custom`) · `system` bool (base roles cannot be deleted).

## authz.groups
`id` · `key` unique · `name` · `description`.

## authz.grants
`id` · `holder_kind` (`role|group`) · `holder_id` · `permission_key` fk · `effect` (`allow|deny`) · `scope_kind` · `scope_ref` null · `created_by` · `created_at`. Unique (holder, permission, scope). Trigger: reserved permissions may only be granted to the `admin` role.

## authz.user_roles / authz.user_groups
`user_id` fk identity.users · `role_id`/`group_id` · `granted_by` · `granted_at` · `revoked_at` null. Partial unique index: at most one active `admin` assignment. Admin assignment rows are append-only (revocation sets `revoked_at` only inside the transfer function).

## authz.admin_singleton
One row (`id=1`, `current_admin_user_id`, `version`) used as the lock target for `transfer_admin`.

## audit.audit_entries (append-only; AuditSink target)
`id` uuid · `seq` bigserial · `occurred_at` · `received_at` · `actor_user_id` null · `actor_kind` (`user|system|ai|automation|plugin`) · `acting_for` null · `action` · `resource_type` · `resource_id` null · `scope` null · `decision` (`allow|deny|n/a`) · `result` (`success|failure|n/a`) · `context` jsonb (redacted, no secrets) · `correlation_id`. Trigger rejects UPDATE/DELETE. Completed in step 3 (hash-chain checkpoints, retention, query) — **same table**.

## authz.confirmations
`token_hash` pk · `principal_user_id` · `permission_key` · `resource_hash` · `expires_at` · `consumed_at`.

## Events (via `EventPublisher`)
`permission.role_assigned|role_revoked|group_changed|permission_granted|permission_revoked|policy_changed|admin_transfer_attempted|denied`. Dedup key: `(holder, permission/role, change_seq)`.

## Implementation notes (2026-10-02)
- `authz.permissions` also carries `user_grantable` (entitlement permissions grantable to one user, F15).
- `authz.grants.holder_kind` also accepts `user` (entitlements only, never reserved); `scope_ref` is `''` when
  unused (part of the unique key); `source` records where a grant came from (`default|admin|marketplace|…`).
- Every account implicitly holds the base `user` role (no row); the Admin is "all enabled permissions minus
  explicit denies"; the single-Admin index is `UNIQUE ((true)) WHERE role_id = <admin> AND revoked_at IS NULL`.
- `audit.audit_entries.actor_kind` also accepts `anonymous` (e.g. failed sign-ins).
- FKs to `identity.users(id)` are created by the migrations only (models do not import another module).

## Lifecycle / retention / privacy
Roles/groups: soft-retire (never hard-delete while assigned). Audit: append-only, retention policy in step 3, `actor_user_id` references the user id so tombstoning keeps integrity (context never holds PII bodies). Grants/assignments reference ids only.
