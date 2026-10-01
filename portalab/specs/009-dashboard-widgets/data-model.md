# Data Model — Dashboard (schema `dashboard`)

## dashboard.user_dashboards
`user_id` PK/FK `identity.users(id)` · `starter_applied_at` null · `last_summary_seen_at` null · `layout_version` int (optimistic concurrency) · `updated_at`.

## dashboard.widget_instances
`id` UUIDv7 · `user_id` FK `identity.users(id)` · `widget_key` · `status` (`active|hidden`) · `position` int · `w` · `h` · `config` jsonb · `config_schema_version` · `origin` (`starter|user|policy_default`) · `created_at` · `updated_at`. Unique `(user_id, widget_key, id)`; a widget definition may allow multiple instances (`multiple: bool`). Removal = hard delete (config discarded). Personal data class `preference`.

## Declared, not stored here
- `WidgetDefinition` / `WidgetDataProvider` / `ChangeSummaryProvider` registrations — in-memory capability registry.
- **Widget policies** — setting `dashboard.widgetPolicies` in 020: `{widget_key: {class: free|default|mandatory|locked|conditional|disabled, condition?, lockedConfig?}}`.
- `dashboard.starterLayout` (list of `{widget_key, w, h, roles?}`), `dashboard.sinceLastLogin.{lookbackDays(30), maxItems(20), inactivityGapMinutes(30), types[]}`, `dashboard.widgetTimeoutMs` (5000).

## Effective dashboard (computed on read)
`effective(user) = overlay(policy, rows)`: remove disabled; add mandatory (and default if not yet applied) without persisting; force locked placement/config; drop conditional widgets whose condition is false; drop widgets whose permission/module is no longer available. Stored rows untouched → relaxing policy restores prior state.

## Config schema versioning
Each `WidgetDefinition` has `config_schema` + version; upgraders migrate stored `config`; invalid config falls back to defaults and is flagged `config_invalid` in the payload.

## Events (via 007)
Produced: `dashboard.layout_changed` (user, counts only; dedup `(user_id, layout_version)`), `dashboard.starter_applied` (dedup `user_id`). Consumed: onboarding step events (002), domain events listed in widgets' `invalidate_on` (→ SSE only), `plugin.state_changed`/marketplace activation (register/unregister widgets), `admin.config_changed` (policy epoch).

## Privacy / retention
Instances are user preference data (export/erase via 020 participant). The summary is computed on demand and not persisted beyond `last_summary_seen_at`.
