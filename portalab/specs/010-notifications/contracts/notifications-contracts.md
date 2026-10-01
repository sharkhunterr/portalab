# Contracts — Notifications

## Python capability `capabilities/notifications`
- `declare_category(key, owner, label_key, default_priority, default_channels, mandatory_channels=(), user_mutable=True)`.
- `send(req: CommunicationRequest, *, caller: Principal | System) -> CommunicationRef` where `CommunicationRequest{kind, category, priority, audience: AudienceSpec, template_key, params, subject_ref?, dedup_key, source, source_ref?, valid_until?, action_url?}`; `AudienceSpec ∈ Users(ids) | WithPermission(key, scope?) | Role(id) | AllAuthenticated`. Caller authority bounds the audience; automations pass `on_behalf_of=author`.
- `send_alert(...)` convenience (kind=alert, priority ≥ high) — also the port `notifications.send_alert` declared by 025.
- `Channel` protocol (`portal`, `email`, `sound`, future `push`): `deliver(notification, prefs) -> DeliveryResult`.
- `EmailTransport` port (SMTP adapter default); `VerificationChannel` email implementation for 002.
- **Automations action contract** (consumed by 019): `ActionType{key: "communication.produce", params_schema, required_permission: notifications.send_to_audience, idempotency: dedup_key from trigger}` registered via `register_action_type`.
- `RecipientLocale.for_user(user_id)` consumed from 026.

## HTTP (`/api/v1`)
| Path | Permission | Notes |
|---|---|---|
| GET `/me/notifications?cursor&category&unread&kind` | `users.self.manage` | owner only; important-first ordering |
| GET `/me/notifications/unread-count` | self | |
| POST `/me/notifications/{id}/read` · `/read-all` · `/archive` · DELETE `/me/notifications/{id}` | self | |
| GET/PUT `/me/notification-preferences` | self | per category/channel + digest; returns policy locks (`mandatory`, `locked`) |
| GET `/notifications/categories` | authenticated | categories with user-facing labels and lock state |
| GET `/admin/notifications/deliveries` · `/admin/notifications/status` | `notifications.manage` | no content, privacy-bounded |
| PUT `/admin/notifications/email` (transport config) · POST `/admin/notifications/email/test` | `notifications.manage` (audited, secret masked) | |
| PUT `/admin/notifications/categories/{key}` | `notifications.manage` (audited) | via 020 policy |
SSE (004): `notification.created {id, kind, priority}`.
Problem codes: `notifications.audience_forbidden`, `notifications.category_unknown`, `notifications.mandatory_channel`.

## Frontend
`<NotificationCenter>` (list, filters, read/archive, priority/kind distinction), `<ToastRegion>` using the 022 `Notification` + `Announce` (alerts assertive; critical persistent until acknowledged), `<NotificationPreferences>` with `PolicyField`, header bell with unread count (004 slot).

## Extension point (023)
Plugins call `declare_category` and `send` through the plugin host; their categories are namespaced `plugin:<id>.*`, never mandatory.
