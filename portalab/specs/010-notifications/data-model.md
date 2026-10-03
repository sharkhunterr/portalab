# Data Model — Notifications (schema `notify`)

## notify.categories (registry mirror; source = `declare_category` + 020 policy)
`key` PK · `owner` · `label_key` · `default_priority` · `default_channels` jsonb · `mandatory_channels` jsonb · `user_mutable` bool · `status`. Seeded at startup from declarations; admin overrides live in 020 policy.

## notify.communications (immutable fact of "something was produced")
`id` UUIDv7 · `kind` (`notification|alert`) · `category` · `priority` (`low|normal|high|critical`) · `source` (`system|admin_rule|event|automation|module`) · `source_ref` · `dedup_key` · unique `(source, dedup_key)` · `template_key` · `params` jsonb (no secrets, reference ids) · `subject_ref` (opaque, no FK) · `audience_spec` jsonb · `produced_by` (principal ref / system) · `valid_until` null · `action_url` null · `created_at`.

## notify.notifications (the notification center — one row per recipient)
`id` · `communication_id` FK · `user_id` FK `identity.users(id)` · `language` · `title` · `body` (rendered text) · `kind` · `category` · `priority` · `count` (coalescing) · `action_url` · `read_at` · `archived_at` · `created_at` · `expires_at`. Index `(user_id, archived_at, priority desc, created_at desc)`. Personal data class `activity`.

## notify.deliveries (per recipient and channel)
`id` · `communication_id` FK · `user_id` FK · `channel` (`portal|email|sound|push`) · `status` (`pending|sent|delivered|failed|suppressed`) · `suppress_reason` (`preference|permission_lost|expired|throttled|policy|no_address`) · `attempts` · `last_error` (sanitized) · `scheduled_for` · `sent_at`. Unique `(communication_id, user_id, channel)`.

## notify.email_outbox
`delivery_id` PK/FK · `to_hash` (never the clear address in logs) · `subject` · `body_text` · `body_html` · `next_attempt_at` · `attempts`. Body removed after successful send (retention minimization).

## notify.maintenance_reminders (system source state)
`maintenance_id` · `schedule_version` · `kind` (`j1|h1|start|corrective`) · `job_ref` · `status` (`scheduled|sent|cancelled|expired`) · unique `(maintenance_id, schedule_version, kind)`.

## notify.digest_state
`user_id` · `last_digest_at` — drives email digest jobs.

## Settings (declared into 020)
Global: `notifications.coalesceWindowSeconds` (120), `notifications.retentionDays` (90), `notifications.email.enabled`, `.email.from`, `.email.smtp.host|port|tls|username` (+ `password` secret), `notifications.email.maxAttempts` (5), `notifications.digest.defaultMode`, category policy (mandatory/default channels). User: `notifications.preferences.<category>.<channel>`, `notifications.email.digest`. Presentation prefs reuse 022 (`ui.notificationPosition|DurationSeconds|Style`, `ui.soundEnabled`).

## Events (via 007)
Consumed: `maintenance.scheduled|rescheduled|started|ended|cancelled` (006, with `schedule_version`), `service.status_changed` (006, critical ⇒ system alert), `user.suspended|reactivated|deletion_requested` (account security), `admin.config_changed`. Produced: `notification.sent` (communication-level counts), `notification.read` (user-level, dedup `(notification_id)`), `notification.delivery_failed` (diagnostic, deduped per channel/min).

## Privacy / retention
Inbox and deliveries are `activity` personal data (export/erasure participant); pending/undelivered follow 021 purge; email bodies purged after send; rendered content excluded from logs/events.

## Implementation notes (2026-10-03)
- Preferences are one user-overridable setting `notifications.preferences` (a `{category: {channel: bool}}`
  dict, 020 config store) plus `notifications.email.digest`; there is no `notify.preferences` table. The
  stored choice is kept when a policy disables a channel and applies again when the policy relaxes.
- Admin policy per category is the global setting `notifications.categoryPolicy`
  (`disabled_channels`, `mandatory_channels`, `locked`), edited through `PUT /admin/notifications/categories/{key}`.
- `notify.categories` mirrors the in-memory owner-tagged registry at start-up (status `active`); the
  registry stays the source of truth (`unregister(owner)` for 023's sweep).
- Fan-out runs synchronously inside `send` (per recipient, each failure isolated); only e-mail goes through
  jobs (`notifications.send_email`, backoff 30 s × 2ⁿ capped at 1 h, `email.maxAttempts`, then `failed` and a
  content-free `notification.delivery_failed` event). The outbox stores the address **hash** only; the clear
  address is read from identity (`identity.contact`) at send time; bodies are deleted once sent.
- Rendering happens per recipient language with the 026 renderer: `template_key` = `namespace:key`, body =
  `key.body` when present. Parameters are plain values (no markup); secret-looking keys are rejected.
- Coalescing merges unread items with the same `(user, category, subject_ref)` within
  `coalesceWindowSeconds` into one item with `count`; critical items are never coalesced.
- The live ping `notification.created` carries ids/kind/priority only (never text).
- `notifications.send` (v2) replaces the 016 slice A placeholder (`support` no longer declares it); 016 and
  017 now send `CommunicationRequest`s in categories `support.incident` / `statistics.wrapped`.
- Identity gained `identity.contact` (e-mail of active accounts, system use only) and the
  `identity.verification_channel` capability; the e-mail `VerificationChannel` sends the token when e-mail
  is enabled and the account has an address, else the Admin hand-off remains.
- OQ-45..49 use the research defaults (R6–R9); product confirmation still open.
