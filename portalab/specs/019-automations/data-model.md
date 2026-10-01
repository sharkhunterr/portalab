# Data Model — Automations (schema `automations`)

FKs only intra-module or to `identity.users(id)`; event/action references are opaque.

- **automations.automations**: `id` UUIDv7 · `key` unique · `name` · `state` (`draft|active|paused|suspended|archived`) · `current_version` · `owner_user_id` FK · `identity_kind` (`author|system`) · `system_scopes` jsonb null · `needs_review` bool · `suspend_reason` null · `consecutive_failures` int · `created_at` · `updated_at`.
- **automations.versions** (append-only): `automation_id` FK · `version` · `definition` jsonb · `published_by` FK · `published_at` · `standing_approvals` jsonb (action types attested) · PK `(automation_id, version)`.
  `definition` = `{trigger{kind: event|at|relative|recurring, event_type?, filter?, reference?, offset?, schedule?, tz?}, conditions{tree}, steps[{id, action, params, on_error}], limits{cooldown_s, dedup_key?, dedup_window_s, batchable, rate_per_min}, schema_version}`; closed schema.
- **automations.executions**: `id` UUIDv7 · `automation_id` FK · `version` · `trigger_event_id` null · `trigger_ref` jsonb (type, subject refs, `occurred_at`) · `chain_id` · `depth` · `status` · `conditions_trace` jsonb · `steps` jsonb (`[{id, action, status, duration_ms, result_ref, error_code}]`) · `batch_count` · `principal` jsonb (kind/user id) · `started_at` · `finished_at` · unique `(automation_id, version, trigger_event_id)` where not null.
- **automations.approvals**: `id` · `execution_id` FK · `step_id` · `action` · `summary` (action-generated) · `params_hash` · `requested_from` (role/user) · `status` (`pending|approved|rejected|expired`) · `decided_by` FK null · `decided_at` null · `expires_at`.
- **automations.schedule_state**: `automation_id` FK · `next_fire_at` · `last_fired_at` — for time triggers; maintained by the scheduler.
- **automations.dedup_windows**: `automation_id` · `dedup_key` · `expires_at` · PK both (pruned).
- **automations.templates**: shipped as code/data files (not a table).

## Settings (declared into 020)
`automations.enabled`, `automations.allowUserAuthoring` (false), `automations.maxSteps` (10), `automations.maxChainDepth` (3), `automations.executionTimeoutSeconds` (30), `automations.actionTimeoutSeconds` (10), `automations.defaultRatePerMinute` (60), `automations.globalConcurrency`, `automations.suspendAfterFailures` (5), `automations.suspendFailureRate` (0.5 over 20), `automations.approvalTtlHours` (72), `automations.executionRetentionDays` (90), `automations.minScheduleIntervalMinutes` (60).

## Events (via 007; no payload bodies)
Produced: `automation.created|published|paused|resumed|suspended|archived`, `automation.approval_requested|approval_decided`. Executions are rows (not events) to avoid storms; consequences of actions are emitted by owner domains with `provenance.automation{id, execution_id, depth}`. Consumed: every `automatable` event type referenced by active automations (idempotent via `ctx.idempotent_effect` + unique execution key), `plugin.state_changed`, `admin.config_changed`, user deactivation/role-change events (re-review).

## Privacy / retention
Definitions/executions carry references and counters only; trigger payload bodies are not stored; retention 90 days for executions, definitions/versions retained; actor ids tombstone-safe.
