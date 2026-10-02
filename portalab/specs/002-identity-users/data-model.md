# Data Model — Identity & Users (schema `identity`)

Conventions from `specs/001-portal-global-spec/data-model.md` apply (UUIDv7, timestamptz UTC, no cross-module FK except to `identity.users`).

## users
Purpose: the account/identity. Owner: identity. Lifecycle: see state machine.
- `id` uuid pk · `login` text (normalized, unique) · `login_display` text · `display_name` text · `display_name_key` text (unique, nullable after deletion) · `email` text null (verified separately) · `state` text CHECK in (`pending_verification`,`active`,`inactive`,`suspended`,`pending_deletion`,`deleted`) · `state_before_deletion` text null · `state_changed_at` · `verified_at` · `last_sign_in_at` · `deletion_requested_at` · `deletion_due_at` · `deleted_at` · `created_at` · `updated_at`.
- PII classes: `login`,`email` = contact/identifier; `display_name` = profile. Tombstone nulls all of them and `display_name_key`; `id` and `state='deleted'` remain.
- Indexes: unique(login), unique(display_name_key) where not null, (state, state_changed_at), (deletion_due_at) where state='pending_deletion'.

## credentials
`user_id` pk/fk · `scheme` (`argon2id`) · `hash` · `params_version` · `changed_at`. Secret class; never exported; deleted at tombstone.

## sessions
`id` uuid pk · `token_hash` (unique) · `user_id` fk · `created_at` · `last_seen_at` · `expires_at` · `revoked_at` null · `revoke_reason` null (`logout|suspended|deleted|admin|password_change`) · `user_agent_summary` · `ip_prefix` (truncated). Technical PII class; pruned by retention.

## login_throttle
`key_hash` (identifier+ip hash) pk · `failures` · `window_start` · `blocked_until`. No raw identifier stored.

## verification_tokens
`id` · `user_id` fk · `token_hash` · `purpose` (`verify`) · `expires_at` · `consumed_at`.

## profiles
`user_id` pk/fk · `avatar_blob_key` null · `bio` etc. are **profile fields**: rows in `profile_fields(user_id, key, value, visibility_preference, updated_at)` — only the *preference* is stored; effective visibility/overrides belong to Privacy (021).

## account_state_history (append-only)
`id` · `user_id` · `from_state` · `to_state` · `actor_id` null · `reason` · `occurred_at` · `received_at`. Trigger-enforced append-only. User history, never public by default.

## deletion_requests
`id` · `user_id` · `requested_by` · `requested_at` · `due_at` · `cancelled_at` null · `finalized_at` null · `saga_state` jsonb (per-participant status).

## onboarding_progress
`user_id` · `step` (`profile|interests|notifications|privacy|dashboard|discovery`) · `completed_at`. Owner: identity tracks progress; each step's *content* belongs to its owning module.

## export_jobs
`id` · `user_id` · `requested_at` · `status` · `blob_key` null · `expires_at`. Bundle stored in blobstore, deleted at `expires_at`.

## Not stored here
Roles/permissions/groups (`authz`, spec 003) · preferences (Administration, user tier) · visibility engine & overrides (021) · audit store (`AuditSink`, introduced in 003) · event store (007).

## Events produced (via `EventPublisher`)
`user.created`, `user.verified`, `user.signed_in`, `user.signed_out`, `user.profile_updated`, `user.deactivated`, `user.reactivated`, `user.suspended`, `user.data_export_requested`, `user.data_exported`, `user.deletion_requested`, `user.deletion_cancelled`, `user.anonymized`, `user.deleted`; `user.admin_transferred` is emitted by the transfer orchestration; `user.onboarding_completed` when every onboarding step is completed.

## Kernel additions made by this spec
`core.event_outbox` (EventPublisher outbox adapter, migration `core_0005`), `core.blobstore` (filesystem, root from the bootstrap setting `DATA_DIR`), `core.audit_port` (interim `LogAuditSink` until 003), `core.authorization` (`require()`/`public` usable by modules), setting `identity.exportTtlHours`.
