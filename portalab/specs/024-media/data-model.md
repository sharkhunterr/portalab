# Data Model — Media (schema `media`)

Cross-module references (`service_id`, `plugin_id`, request source) are opaque ids **without FKs**; FKs only intra-module or to `identity.users(id)`.

## Catalog & identity
- **media.objects**: `id` UUIDv7 · `kind` (registered MediaType) · `parent_id` FK self (series→season→episode, album→track) · `position` null · `effective` jsonb (title, original_title, overview, year/dates, durations, genres, language, image refs, …) · `field_provenance` jsonb · `status` (`active|hidden|merged`) · `merged_into` FK self null · `first_seen_at` · `created_at` · `updated_at`.
- **media.external_ids**: `object_id` FK · `scheme` · `value` · unique `(scheme, value)` (strong ids only).
- **media.field_candidates**: `object_id` FK · `field` · `source_system` · `source_item_id` FK · `value` jsonb · `observed_at` · PK `(object_id, field, source_system)`; `source_system='admin'` = override.
- **media.object_tags**: `object_id` FK · `tag_kind` (`genre|tag|keyword|person`) · `value` · for filters/search.
- **media.match_candidates**: `id` · `object_a` · `object_b` · `score` · `evidence` jsonb · `state` (`proposed|accepted|rejected`) · decided_by/at.
- **media.merge_log** (append-only): merge/split actions with before/after pointers (reversibility, audit).
- **media.source_items**: `id` · `object_id` FK null (until resolved) · `service_id` · `capability` · `source_system` · `external_id` · `active` bool · `availability` (`available|unavailable|unknown`) · `payload` jsonb (sanitized, no secrets) · `payload_hash` · `first_seen_at` · `last_seen_at`. Unique `(service_id, external_id)`.
- **media.images**: `id` · `object_id` FK · `role` (`poster|backdrop|thumb`) · `blob_key` · `content_hash` · `source_item_id`.

## Playback & history
- **media.user_links**: `user_id` FK `identity.users(id)` · `service_id` · `external_user_id` · `verified` bool · unique `(service_id, external_user_id)`.
- **media.playback_sessions**: `session_key` PK · `user_id` FK null (unlinked) · `object_id` FK null · `service_id` · `state` (`playing|paused|buffering|stopped|stale|interrupted`) · `position_s` · `duration_s` · `device` null · `started_at` · `updated_at` · `as_of` · `state_seq` int.
- **media.history_entries** (projection, append-only, rebuildable): `id` · `user_id` FK · `object_id` FK · `kind` (`session|progress|finished`) · `source_system` · `session_key` null · `position_from_s` · `position_to_s` · `consumed_s` · `completed` bool · `occurred_at` · `received_at`. Index `(user_id, occurred_at desc)`, `(object_id, occurred_at)`.
- **media.user_progress** (derived): `user_id` · `object_id` · `resume_position_s` · `percent` · `state` (`in_progress|finished`) · `last_occurred_at`. PK `(user_id, object_id)`.

## Requests
- **media.requests**: `id` · `object_id` FK null · `external_ref` jsonb (scheme/value when not in catalog) · `requester_user_id` FK · `service_id` · `external_request_id` · `state` (`pending|approved|declined|processing|available|failed|cancelled`) · `source_state` · `requested_at` · `updated_at`. Unique `(service_id, external_request_id)`.

## Registries (in memory) / Settings (020)
`MediaType`, detail-page slots, `RecommendationProvider`, `RequestQuotaProvider` port. Settings: `media.fieldPriority.<kind>.<field>` (ordered source systems), `media.finishedThreshold.<kind>`, `media.playback.pollActiveSeconds` (15) / `.pollIdleSeconds` (60) / `.staleTimeoutSeconds` (120) / `.progressEventSeconds` (60), `media.requests.quotaPerPeriod`, `media.requests.period`, `media.match.autoThreshold`, `media.discovery.*`.

## Events (via 007; payload = ids/counters only)
Produced: `media.item_added`, `media.item_availability_changed`, `media.merged`, `media.split`, `media.playback_started|progressed|paused|resumed|stopped|interrupted`, `media.finished`, `media.request_created|updated|fulfilled`. Dedup: `(session_key, state_seq)`, `(user_id, object_id, finished)`, `(request_id, state)`. Consumed: connector sync results via RecordSinks (not events), `service.state_changed` (006), `identity` erasure participant.

## Privacy / retention
`history_entries`, `user_progress`, `user_links`, `requests`(requester), sessions = personal data (`activity`/`media_history`); erased/anonymized by 020/021 participant (objects and aggregates unaffected); history retention per 021.
