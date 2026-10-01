# Data Model — Events & History (schema `events`)

## events.events (append-only, monthly range partitions on `occurred_at`)
`event_id` uuid · `seq` bigint (identity) · `type` · `type_version` · `occurred_at` · `received_at` · `source_system` · `source_event_id` null · `source_ref` jsonb null · `actor_user_id` null · `actor_kind` · `subject_type` · `subject_id` null · `service_id` null · `object_seq` bigint null · `payload` jsonb (validated, no PII/secrets) · `provenance` jsonb · `correlation_id` · `visibility_class`.
Indexes: (seq); (type, occurred_at); (subject_type, subject_id, occurred_at); (actor_user_id, occurred_at).

## events.dedup_keys
`type` · `dedup_key` · `event_id` · `first_seen_at`. Unique (type, dedup_key). Pruned by `events.dedupKeyRetention` (default = event retention).

## events.quarantine
`id` · `received_at` · `reason` (`unknown_type|invalid_payload|version_unsupported|pii_detected`) · `raw` jsonb (redacted) · `source_system` · `status` (`open|released|discarded`).

## events.consumer_offsets
`consumer` pk · `last_seq` · `updated_at`.

## events.deliveries
`consumer` · `event_id` · `status` (`pending|succeeded|failed|dead`) · `attempts` · `last_error` (redacted) · `updated_at`. Unique (consumer, event_id).

## events.effect_keys
`consumer` · `effect_key` · `created_at`. Unique (consumer, effect_key) — idempotent side effects (rewards, notifications, purchases).

## events.replay_runs
`id` · `projection` · `from_occurred_at` · `to_occurred_at` · `requested_by` · `status` · `started_at` · `finished_at`.

## Registries (code)
`EventType` (name, version, schema with per-field annotations `rewardable` (013) / `aggregatable` (017), `automatable` flag (019), owner tag, dedup_fields/source-id flag, retention_class `business|technical`, visibility_class), `Consumer` (name, event types, handler, replay_safe).

Envelope conventions: `actor_kind` ∈ `user|system|ai|automation|plugin`; `provenance.automation{id, execution_id, depth}` set by actions run by 019 (loop prevention).

## Lifecycle / retention / privacy
Events immutable; retention by dropping partitions per class (021 engine; `business` kept long, `technical` short; both configurable); personal events reference `actor_user_id` only (tombstone safe); history is owner-only by default (021). Deleted-user events remain with the same id.

## Events produced by this module
`events.quarantined`, `events.consumer_dead_lettered`, `events.replay_started|finished`.
