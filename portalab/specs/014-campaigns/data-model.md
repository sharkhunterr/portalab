# Data Model — Campaigns (schema `campaigns`)

FKs only intra-module or to `identity.users(id)`; `theme_key`, achievement/quest ids are opaque references.

- **campaigns.campaigns**: `id` UUIDv7 · `key` unique · `state` (`draft|scheduled|active|paused|ended|archived`) · `current_version` int · `timezone` · `created_by` FK · `created_at` · `archived_at` null.
- **campaigns.versions** (append-only): `campaign_id` FK · `version` · `effective_from` timestamptz · `definition` jsonb · `created_by` FK · `created_at`. PK `(campaign_id, version)`.
  `definition` = `{name_key|names, description, schedule{start_at, end_at|duration, recurrence{kind, anchor, params}, all_day}, modifiers[{id, value, factor, when{media_kind[], genre[], title_contains[], activity[], audience{…}}}], achievements[], quests[], theme{theme_key, presentation_priority}, announcements[] (preset templates only), ending_soon_hours}`; closed schema, `schema_version`.
- **campaigns.occurrences**: `id` · `campaign_id` FK · `version` · `index` · `start_at` · `end_at` · `status` (`planned|active|ended|skipped|cancelled`). Unique `(campaign_id, index)`.
- **campaigns.activation_log** (append-only; closed intervals only): `id` · `campaign_id` FK · `version` · `occurrence_id` FK null · `during` tstzrange (closed, `[opened, closed)`) · `cause` (`schedule|manual`) · `actor_user_id` FK null · `reason` null. **EXCLUDE USING gist (campaign_id WITH =, during WITH &&)** prevents overlapping intervals. Rows are inserted once, when an interval closes; they are never updated.
- **campaigns.open_intervals**: `campaign_id` PK · `version` · `opened_at` · `cause` · `actor_user_id` null · `occurrence_id` null — the single currently open interval. Eligibility at `occurred_at` = `∃ log.during ∋ at` **or** `open.opened_at ≤ at`; closing moves the row into `activation_log` in one transaction.
- **campaigns.overrides**: `id` · `campaign_id` FK · `kind` (`activate|deactivate`) · `from_at` · `until_at` null (auto-expiry per R4) · `actor_user_id` FK · `reason` · `created_at` · `expired_at` null.
- **campaigns.attribute_failures** (bounded counters): `day` · `event_type` · `count` — diagnostic for provider unavailability.

## Settings (declared into 020)
`campaigns.endingSoonHours` (24), `campaigns.maxActiveCampaigns` (soft warning), `campaigns.reconcileSeconds` (60), `campaigns.historyRetention` (long); cap value is `economy.maxTotalBoost` (013).

## Events (via 007; no PII)
Produced: `campaign.created`, `campaign.version_published`, `campaign.scheduled`, `campaign.started`, `campaign.ending_soon`, `campaign.ended`, `campaign.paused`, `campaign.resumed`, `campaign.cancelled`, `campaign.archived` (dedup `(campaign_id, occurrence_id, transition)`). Consumed: `admin.config_changed` (tz/policy), `plugin.state_changed` (theme/provider availability).

## Privacy / retention
Campaign data is non-personal (actor ids tombstone-safe). History (versions, activation_log, overrides) retained long-term for grant provenance; no secrets in definitions.
