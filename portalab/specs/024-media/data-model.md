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
- **media.request_quota_units**: `user_id` FK · `units_remaining` bigint CHECK ≥ 0 · `updated_at` · PK `user_id` — extra units credited by Marketplace purchases.
- **media.request_quota_ledger** (append-only): `id` · `user_id` FK · `delta` · `reason` (`purchase|refund|consumption|admin`) · `source_ref` · `idempotency_key` unique · `created_at`.
- **media.requests**: `id` · `object_id` FK null · `external_ref` jsonb (scheme/value when not in catalog) · `requester_user_id` FK · `service_id` · `external_request_id` · `state` (`pending|approved|declined|processing|available|failed|cancelled`) · `source_state` · `requested_at` · `updated_at`. Unique `(service_id, external_request_id)`.

## Registries (in memory) / Settings (020)
`MediaType`, detail-page slots, `RecommendationProvider`, `RequestQuotaService` (owned here; Marketplace only credits/debits units). Settings: `media.fieldPriority.<kind>.<field>` (ordered source systems), `media.finishedThreshold.<kind>`, `media.playback.pollActiveSeconds` (15) / `.pollIdleSeconds` (60) / `.staleTimeoutSeconds` (120) / `.progressEventSeconds` (60), `media.requests.quotaPerPeriod`, `media.requests.period`, `media.match.autoThreshold`, `media.discovery.*`.

## Events (via 007; payload = ids/counters only)
Produced: `media.added|updated|removed`, `media.availability_changed`, `media.merged|split` (portal-native identity events), `media.playback_started|progressed|paused|finished|abandoned|error` (resume ⇒ `progressed`; session ended at/above the finished threshold ⇒ `finished`, below ⇒ `abandoned`; source lost ⇒ `error`), `media.resume_available`, `media.request_created|updated|available` — names as listed in spec 024 / EVENT_MODEL. Dedup: `(session_key, state_seq)`, `(session_key, 'finished')`, `(request_id, state)`. Consumed: connector sync results via RecordSinks (not events), `service.status_changed` (006), `identity` erasure participant.

## Privacy / retention
`history_entries`, `user_progress`, `user_links`, `requests`(requester), sessions = personal data (`activity`/`media_history`); erased/anonymized by 020/021 participant (objects and aggregates unaffected); history retention per 021.

## Implementation notes (2026-10-09)
- `media.objects` materializes `title`, `sort_title`, `year` and `available` for browsing/filtering; the
  effective fields and their provenance stay in `effective` / `field_provenance`.
- `media.images` keeps the source ref of the stored poster (re-fetched only when the ref changes); images are
  fetched by the `media.fetch_image` job through the service's `media.library` provider.
- `media.user_links` is unique per `(service_id, external_user_id)` **and** per `(user_id, service_id)`;
  only verified links attribute activity (verification by the service's `verify_user`, else an Admin).
- `media.playback_sessions` adds `kind`, `max_position_s` (finished threshold), `last_event_at` (progress
  throttle) and `ended`; sessions started while an account was unlinked stay unattributed.
- `media.history_entries.event_id` is unique: replays and redeliveries are no-ops; `user_progress` is
  recomputed from history after a merge/split.
- `media.requests` adds `idempotency_key` (per user) and `counted` (`base|extra|none`); the request ledger
  is append-only by code (no trigger) so account erasure can delete it.
- Settings: `media.fieldPriority.<kind>.<field>` are declared for the baseline kinds and the fields
  `title, overview, year, genres, image`; `media.finishedThreshold.<kind>` for kinds with a threshold.
- New kernel capability `activity.attributes` (014 contract) with Media as first provider.
- OQ-115..119 use the research defaults (R2, R3, R8, R9, R13); product confirmation still open.
