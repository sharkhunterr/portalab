# Data Model — Services & Health (schema `health`)

## health.service_state (current, one row per service)
`service_id` pk (logical id of `connectors.services`) · `state` (`operational|degraded|unavailable|maintenance|unknown`) · `state_since` · `state_seq` · `last_check_at` · `last_ok_at` · `reason` (`probe|breaker|stale|maintenance`) · `maintenance_id` null.

## health.state_history (append-only)
`id` · `service_id` · `from_state` · `to_state` · `occurred_at` · `received_at` · `reason`.

## health.health_samples (partitioned, short retention)
`service_id` · `checked_at` · `ok` · `latency_ms` · `error_code` null · `detail` jsonb (redacted).

## health.health_rollups
`service_id` · `bucket_start` (hour) · `samples` · `ok_samples` · `p95_latency_ms` · `downtime_seconds`. Unique (service, bucket).

## health.recent_errors
`id` · `service_id` · `occurred_at` · `code` · `message` (actionable, redacted) · `count` · `last_seen_at`.

## health.maintenance_windows
`id` · `service_id` null (null = portal-wide) · `title` · `description` · `starts_at` · `ends_at` · `status` (`scheduled|active|ended|cancelled`) · `created_by` · `created_at` · `cancelled_at` null. Instants absolute (UTC); reference time zone stored when wall-clock was intended.

## health.infra_samples (partitioned, short retention)
`service_id` · `metric` · `value` · `unit` · `sampled_at` · `available` bool.

## Links (logical ids, no FK)
`incident_id`, `ticket_id` references live in Support; 006 stores only `health.service_incident_links(service_id, incident_id, linked_at)`.

## Events
`service.status_changed` (dedup `(service_id, to_state, state_seq)`), `service.health_recorded`, `maintenance.scheduled|rescheduled|started|ended|cancelled` (payload carries `schedule_version`), `service.operation_performed`.

## Retention / privacy
Samples and infra samples are technical class (days/weeks, config); rollups and state history longer; no personal data. Error messages redacted.
