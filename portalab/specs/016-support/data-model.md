# Data Model — Support (schema `support`)

FKs only intra-module or to `identity.users(id)`; `service_id`, `plugin_id` are opaque ids.

## Incidents (Slice A)
- **support.incidents**: `id` UUIDv7 · `number` (serial, `INC-0001`) · `title` · `summary` (public text) · `severity` (`minor|major|critical`) · `state` (`investigating|identified|monitoring|resolved`) · `source` (`manual|observability|health`) · `dedup_key` null · unique `(source, dedup_key)` · `created_by` FK null (system) · `created_at` · `resolved_at` null · `version`.
- **support.incident_services**: `incident_id` FK · `service_id` (opaque) · PK both.
- **support.incident_updates** (append-only): `id` · `incident_id` FK · `state` · `message` · `author_user_id` null · `created_at` · `update_seq`.
- **support.incident_evidence**: `incident_id` · `evidence_ref` (opaque pointer to 025 anomaly/finding, no payload).

## Tickets (Slice B)
- **support.ticket_types**: `key` PK · `label_key` · `workflow_key` · `fields` jsonb (field defs incl. `private`) · `enabled` · `version`.
- **support.workflows**: `key` · `version` · `definition` jsonb (states, transitions, guards) · PK `(key, version)` · append-only versions.
- **support.tickets**: `id` · `number` (serial `T-000123`) · `type_key` · `workflow_version` · `state` · `title` · `description` · `requester_id` FK · `assignee_id` FK null · `priority` (`low|normal|high|urgent`) · `fields` jsonb · `service_id` null · `incident_id` FK null · `source` (`manual|ai_diagnosis|feedback_conversion`) · `feedback_id` FK null · `technical_context` jsonb (snapshot refs/as_of, no secrets) · `version` · `created_at` · `updated_at` · `closed_at` null.
- **support.ticket_tags**: `ticket_id` · `tag` · PK both. Index for filtering.
- **support.ticket_comments**: `id` · `ticket_id` FK · `author_id` FK · `body` · `internal` bool · `created_at` · `edited_at` null.
- **support.ticket_history** (append-only): `id` · `ticket_id` FK · `seq` · `kind` (`created|transition|assignment|field_changed|tag|incident_linked|comment_added`) · `actor_id` · `data` jsonb · `created_at`. Unique `(ticket_id, seq)`.
- **support.attachments**: `id` · `ticket_id` FK · `comment_id` FK null · `uploaded_by` FK · `blob_key` · `filename` (sanitized) · `content_type` (sniffed) · `size` · `sha256` · `created_at`.
- **support.ticket_drafts**: `id` · `user_id` FK · `payload` jsonb · `source` (`ai`|`manual`) · `diagnosis_run_id` null · `expires_at` (short TTL).
- **support.diagnosis_runs**: `id` · `user_id` FK · `steps` jsonb (`[{name, status, kind: real|ai, refs[], as_of}]`) · `outcome` (`resolved|ticket_prefilled|inconclusive|failed`) · `created_at`.

## Feedback (Slice B)
- **support.feedback_forms**: `key` · `kind` · `fields` jsonb · `enabled` · `version`.
- **support.feedback_items**: `id` · `form_key` · `form_version` · `submitter_id` FK · `payload` jsonb (validated) · `status` (`new|reviewed|converted|dismissed`) · `reviewed_by` FK null · `created_at`.
- **support.feedback_conversions** (append-only): `id` · `feedback_id` FK · `target_kind` (`ticket|contribution|feature_proposal|community_project`) · `target_ref` · `converted_by` FK · `converted_at`. Unique `(feedback_id, target_kind)`.

## Settings (declared into 020)
`support.attachments.maxBytes|maxPerPost|allowedTypes`, `support.ticketRetentionMonths` (24), `support.reopenWindowDays` (14), `support.draftTtlMinutes` (60), `support.incident.precheckMatchMode`, `support.sla.*` (display only, no enforcement in v1).

## Events (via 007; ids/state only)
Produced: `incident.created|updated|resolved` (dedup `(incident_id, update_seq)`), `ticket.created|updated|assigned|state_changed|reopened|resolved|closed` (`ticket.updated` for field/tag/comment changes, EVENT_MODEL) (dedup `(ticket_id, seq)`), `feedback.submitted|converted` (dedup `(feedback_id, target_kind)`). Consumed: `observability` escalations (via port, not events), `service.status_changed` (006, optional suggestions), `user` erasure participant calls.

## Privacy / retention
Personal data: ticket text/comments (`content`), requester/assignee refs, attachments; private custom fields; internal notes staff-only. Retention by 021 (`support.ticketRetentionMonths`); history append-only; erasure tombstones requester and removes attachments/private fields per participant.

## Implementation notes — Slice A (2026-10-03)
- `support.incident_services` is mapped as `IncidentServiceLink`; `incident_updates` also records the
  `severity` at each step (the timeline shows severity changes); `incidents` keeps `summary` (public text),
  `updated_at` and `version` (optimistic concurrency, `If-Match`). Number = sequence `incident_number_seq`.
- Sources: `manual | observability | health | automation`. 025 escalations without an explicit
  `dedup_key` are deduplicated on `anomaly:<anomaly_id>`.
- The `support.incidents` port keeps its declaration in `capabilities/health.py` (declared with 006) and
  is extended additively (`service_ids`, `dedup_key`, `summary`, `get`); severity accepts 025's
  `info|warning|critical` (mapped to `minor|major|critical`).
- Incidents hold no personal data besides staff author ids (pseudonymous, kept after erasure): no
  export/erasure participant in Slice A. Notification category `support.incident` is used through the
  `notifications.send` port declared here (unprovided until 010); registration of the category with 010
  happens when 010 lands.
- T038/T039 (shared upload helper, automation-callable create + 019 action types) are Slice B / later.
