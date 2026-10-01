# Data Model — Statistics (schema `stats`)

## stats.definitions (append-only versions)
`key` · `version` int · `status` (`draft|active|retired`) · `domain` · `definition` jsonb (validated `StatisticDefinition`) · `change_policy` (`forward_only|rebuild`) · `source` (`builtin|admin|plugin:<id>`) · `created_by` FK `identity.users(id)` · `created_at`. PK `(key, version)`; append-only trigger; current = highest active version.

## StatisticDefinition (document)
`key, title_key, description_key, domain, scope (personal|community|global), event_types[], filter (closed predicate over aggregatable fields), measure{kind, field?}, dimensions[], granularity (day), period_options[], viz{type, options}, hideable, required_permission, min_cohort_size, unlock?{condition tree, relock}, sources[], stale_after_s, schema_version`.

## stats.buckets (derived, rebuildable)
`stat_key` · `def_version` · `scope_type` (`personal|community`) · `scope_id` (user id for personal, null for community) · `bucket_day` date (statistics tz) · `dims_hash` · `dims` jsonb · `count` bigint · `sum` numeric · `min` numeric · `max` numeric. PK `(stat_key, def_version, scope_type, scope_id, bucket_day, dims_hash)`. Global scope = aggregation over community rows at read time.

## stats.members (derived; for exact distinct counts)
`stat_key` · `def_version` · `scope_type` · `scope_id` · `bucket_day` · `member_hash` (salted hash of the distinct subject). PK of all columns. Pruned with bucket retention.

## stats.unlocks
`user_id` FK · `stat_key` · `unlocked_at` · `reason` (condition snapshot). PK `(user_id, stat_key)`. Only for non-relocking conditions.

## stats.wrapped_definitions / stats.wrapped_snapshots
Definitions: `key`, `period_kind` (`month|quarter|year`), `stat_keys[]`, `status`, `version`. Snapshots (immutable): `id`, `wrapped_key`, `period_start`, `period_end`, `subject_scope` (`user|community`), `user_id` null, `payload` jsonb (computed StatResults + definition versions), `generated_at`, `delivered_at` null. Personal snapshots are `activity` personal data (erased/exported with the account).

## stats.rebuild_runs
`id`, `stat_key`, `from_date`, `to_date`, `requested_by`, `status`, `started_at`, `finished_at`, `reason` — audit of replays.

## Settings (declared into 020)
Global: `statistics.timezone`, `statistics.firstDayOfWeek`, `statistics.defaultMinCohortSize` (5), `statistics.staleAfterSeconds` (900), `statistics.maxBucketsPerRequest` (800), `statistics.bucketRetentionMonths` (36), `statistics.wrapped.enabled`. User: `statistics.hiddenSections[]` (only for hideable sections).

## Events (via 007)
Consumed: all event types referenced by active definitions (consumer set rebuilt on definition/plugin changes), `admin.config_changed` (tz/first day), `plugin.state_changed`. Produced: `statistics.definition_changed`, `statistics.unlocked` (user; dedup `(user_id, stat_key)`), `statistics.wrapped_generated` (dedup `(wrapped_key, subject, period)`).

## Privacy / retention
Buckets/members carry no PII (subject ids only inside salted hashes or as personal scope ids governed by erasure: personal buckets deleted on erasure, community aggregates retained anonymously above threshold). Retention by 021 engine; Wrapped snapshots with the account.
