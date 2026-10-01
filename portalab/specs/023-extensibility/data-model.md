# Data Model — Extensibility (schema `plugins`; plus per-plugin schemas `plugin_<key>`)

- **plugins.plugins**: `key` PK · `name` · `scope` (`portal|user`) · `maturity` · `state` (`installed|needs_configuration|enabled|disabled|update_pending|update_failed|incompatible|quarantined|archived`) · `current_version` · `source` (`admin_upload|local_dir|marketplace`) · `needs_restart` bool · `installed_by` FK `identity.users(id)` · `installed_at` · `enabled_at` null · `quarantine_reason` null · `last_error_at` null · `updated_at`.
- **plugins.versions** (append-only): `plugin_key` FK · `version` · `manifest` jsonb · `package_path` · `sha256` · `status` (`current|previous|staged|failed|probation`) · `installed_at` · `probation_until` null · PK `(plugin_key, version)`.
- **plugins.contributions** (ledger): `plugin_key` FK · `point` · `contribution_id` · `state` (`active|removed|conflict`) · `priority` int · `registered_at` · `removed_at` null. Rebuilt at startup for enabled plugins; used for clean removal and diagnostics.
- **plugins.reviews**: `plugin_key` · `version` · `approved_by` FK · `approved_at` · `permissions` jsonb · `extension_points` jsonb · `events` jsonb · `personal_data` bool · `capabilities` jsonb — the install-time consent record.
- **plugins.error_stats** (bounded): `plugin_key` · `window_start` · `kind` (`route|event|action|widget|job|load`) · `count` · `last_sample` (sanitized, no secrets) · PK `(plugin_key, window_start, kind)`.
- **plugins.purges** (append-only): `plugin_key` · `requested_by` FK · `exported` bool · `export_ref` null · `executed_at` · `schema_dropped` bool.
- **plugins.update_runs**: `id` · `plugin_key` · `from_version` · `to_version` · `status` (`staged|migrated|pending_restart|probation|succeeded|rolled_back|failed`) · timestamps · `error` (sanitized).
- **Module registry** (first-party modules) is code metadata (`ModuleDescriptor{key, requires, provides}`); module enabled state lives in 020 toggles.

## Per-plugin storage
Schema `plugin_<key>` + PostgreSQL role `plugin_<key>` (grants only on that schema; `statement_timeout`, `idle_in_transaction_session_timeout`); migrations on an Alembic branch `plugin_<key>` run by the platform with the plugin's own role; **no FKs to core tables** (opaque ids).

## Settings (declared into 020)
`plugins.enabled`, `plugins.directory`, `plugins.errorThreshold` (5 / 10 min), `plugins.hookTimeoutSeconds` (10), `plugins.statementTimeoutMs`, `plugins.updateProbationMinutes` (10), `plugins.requireReview` (true), `plugins.contributionPriority.<key>`; plugin-declared settings appear under scope `plugin`.

## Events (via 007; no secrets)
Produced: `plugin.installed|enabled|disabled|updated|update_failed|rolled_back|quarantined|archived|purged|configuration_changed` and the umbrella `plugin.state_changed {plugin_key, from, to, reason}` consumed by 004, 009, 008, 015, 018, 019, 017, 026 registries. Dedup `(plugin_key, seq)`. Plugin-produced events: `plugin.<key>.<type>` (validated by 007).
Consumed: `admin.config_changed` (plugin settings), Marketplace activation calls (via port), erasure participant registration checks.

## Privacy / retention
Plugin data follows 021 through the manifest's classification and mandatory `erasure_participant` when `personal_data=true` (load refused otherwise); metadata tables contain no personal data except actor ids.
