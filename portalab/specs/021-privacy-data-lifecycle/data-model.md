# Data Model — Privacy & Audit completion

## privacy.visibility_policies
`id` · `subject_user_id` null (null = global class policy) · `datum_class` · `mode` (`user_choice|force_visible|force_private`) · `level` null (target level when forced: `public|community|leaderboards_only|private`) · `reason` · `set_by` · `set_at` · `ends_at` null · `removed_at` null · `removed_by` null. Partial unique index: one active row per (`subject_user_id`, `datum_class`). Rows are history (never deleted); effective policy = row with `removed_at is null and (ends_at is null or ends_at > now())`.
PII: `subject_user_id` is an id only. Audited on apply/remove.

## privacy.retention_runs (append-only)
`id` · `target` · `data_class` · `action` · `rows_affected` · `cutoff` · `run_at` · `status`.

## audit.audit_checkpoints (append-only)
`id` · `from_seq` · `to_seq` · `batch_hash` · `prev_checkpoint_hash` · `checkpoint_hash` · `created_at`. Verified by `portalab audit verify`.

## audit.audit_entries (from spec 003) — changes in this step
Converted to **monthly range partitions** on `occurred_at` (expand/contract migration); same columns; maintenance role may drop partitions older than retention; no row UPDATE/DELETE.

## Registries (in code, not tables)
`RetentionTarget` (table, class, timestamp column, action `delete|anonymize|aggregate|drop_partition`, `integrity_necessary`) · `DataClass` (`personal|activity|technical|history|audit|aggregate`) · `ErasureParticipant`/`ExportContributor` (contracts from spec 002).

## Rules enforced by tests
Append-only tables contain no PII-class columns · every mutable table with PII is classified · retention never targets `integrity_necessary` tables · aggregate endpoints use `AggregationGuard`.

## User visibility preferences
Stored as user-tier settings `privacy.visibility.<datum_class>` in 020 (CD-011), read through `VisibilityPreferenceProvider`; datum classes are registered by owning modules via `register_datum_class(key, owner, default_level, classification)`. Admin overrides never overwrite them (CD-016).

## Events
`privacy.override_applied`, `privacy.override_removed`, `privacy.retention_applied`, `service.data_purged`, `audit.checkpoint_created`, `audit.verification_failed`.
