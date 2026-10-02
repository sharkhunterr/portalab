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

## Implementation notes (2026-10-02)
- `services` also stores `state_seq` (event dedup `(service_id, to_state, state_seq)`) and `state_reason`
  (redacted); credentials are one `SecretBox` token per secret field bound to `connectors.service:<id>:<field>`,
  erased on disconnect. "Syncing" is never persisted as a service state: it is `sync_state.status = running`
  (exposed as `display_state`), keeping sync state apart from health.
- `sync_runs` rows are written once when a run ends; UPDATE/TRUNCATE are rejected by trigger and only the
  021 retention window (`technical` class) deletes. `sync_state.cursor` is keyed by capability.
- `discovery_candidates` also stores `service_id` once confirmed; `(connector_key, target)` is unique so a
  declined candidate is re-offered by a later discovery of the same target.
- Contracts live in `portalab.capabilities` (`connector_sdk`, `connector_http`, `record_sink`,
  `record_sink_testkit`, `automation_actions`) so connector packages and plugins never import the module.
- Field priorities are read from `media.fieldPriority.<kind>.<field>` (024, CD-026) — no
  `connectors.fieldPriority` setting is declared (F7).
