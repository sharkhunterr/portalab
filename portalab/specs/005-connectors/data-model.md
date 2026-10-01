# Data Model — Connectors (schema `connectors`)

## connectors.services
`id` · `connector_key` · `name` · `config` jsonb (non-secret) · `credentials` (encrypted envelope) · `state` (`configured|enabled|syncing|error|unavailable|maintenance|disabled|disconnected`) · `state_changed_at` · `enabled_at` · `disabled_at` · `disconnected_at` · `sync_interval_seconds` null · `created_by` · `created_at` · `updated_at`. Credentials are secret-class; never exported.

## connectors.service_capabilities
`service_id` · `capability` · `enabled` · `priority` int. Unique (service, capability).

## connectors.sync_state
`service_id` pk · `last_attempt_at` · `last_success_at` · `status` (`idle|running|failed`) · `cursor` jsonb · `next_run_at` · `consecutive_failures`.

## connectors.sync_runs (append-only history)
`id` · `service_id` · `capability` null · `kind` (`scheduled|manual|resync_partial|resync_full`) · `triggered_by` null · `started_at` · `finished_at` · `status` · `added` · `modified` · `removed` · `ignored` · `errored` · `last_error` (redacted) · `partial` bool.

## connectors.discovery_candidates
`id` · `connector_key` · `target` · `details` jsonb · `status` (`candidate|confirmed|declined`) · `found_at`.

## connectors.compatibility_checks
`id` · `connector_key` · `portal_version` · `result` · `reasons` jsonb · `checked_at`.

## Registries (code)
`Connector` definitions + manifests · capability Protocol bindings · `RecordSink` registry (capability → sink).

## Events
`service.connected`, `service.disconnected`, `service.status_changed`, `sync.started|completed|failed`, `connector.discovered`, `connector.compatibility_checked`, `connector.resync_requested`. Dedup: `(service_id, run_id)` / `(service_id, to_state, state_seq)`.

## Lifecycle / privacy
Disabling/disconnecting keeps all rows; purge is a separate 021 action (`services.purge`). Service config may hold hostnames (technical), never user PII. Sync history retention via 021 engine (technical class).
