# Data Model — Observability (schema `obs`)

## obs.component_health (current)
`component` pk (e.g. `events`, `sync:<service>`, `automations`, `plugin:<id>`, `connector:<service>`, `ai`, `jobs`, `db`, `portal`) · `technical` (`ok|degraded|down|unknown`) · `functional` (`ok|degraded|failing|unknown`) · `since` · `reason` jsonb · `evaluated_at`.

## obs.health_history (append-only)
`id` · `component` · `axis` · `from_state` · `to_state` · `occurred_at` · `reason`.

## obs.metric_samples (partitioned, short retention)
`component` · `metric` · `labels` jsonb · `value` · `sampled_at`. Phases for performance: `phase ∈ {portal_wait, external_wait, internal, timeout}`.

## obs.rollups
`component` · `metric` · `bucket` (hour/day) · `count` · `sum` · `p95` · `max`. Trends source.

## obs.errors
`id` · `fingerprint` unique · `component` · `service_ref` null · `plugin_ref` null · `event_ref` null · `user_ref` null (only when permitted/necessary, id) · `category` · `level` · `message` (redacted) · `context` jsonb (redacted) · `count` · `first_seen_at` · `last_seen_at` · `state` (`open|acknowledged|resolved`) · `resolution` null · `resolved_by` null.

## obs.anomalies
`id` · `detector` · `component` · `fingerprint` · `severity` · `status` (`candidate|pending_validation|escalated|dismissed|resolved`) · `detected_at` · `evidence` jsonb · `incident_ref` null · `validated_by` null.

## obs.contributions (registry in code, table for state)
`contribution_id` · `owner` (`module|plugin|connector`) · `kind` · `declared_at` · `enabled`.

## Events (via 007 for important ones)
`observability.health_changed`, `observability.error_recorded` (first occurrence/state change only), `observability.anomaly_detected`, `observability.alert_raised`, `observability.diagnostic_action_performed` (actions are executed and audited by owners).

## Retention / privacy
Samples days, rollups months, errors until resolved + retention window (all config, technical class via 021); contexts redacted, secrets never stored; `user_ref` is an id and removed/nulled by erasure participant; no AI content.
