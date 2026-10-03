# Notifications (spec 010)

Notifications are **produced** by modules, system sources and automations through one port, then **delivered**
per recipient on the channels their preferences and the administrator's policy allow. The portal center is
the source of truth; e-mail is an optional second channel; toasts are only a presentation of new items.

## Concepts

| Concept | What it is |
| --- | --- |
| Communication | One request (`category`, `template_key`, `audience`, `dedup_key`…), unique per `(source, dedup_key)` |
| Notification | Information in the center (`kind=notification`) |
| Alert | Urgent item (`kind=alert`, priority `high` or `critical`), announced assertively |
| Delivery | One row per `(communication, user, channel)` — `delivered`, `pending`, `sent`, `failed`, `suppressed(reason)` |
| Category | Declared by its owner module (`owner.name`); plugins use `plugin:<key>.<name>` and can never be mandatory |

Built-in categories: `system.maintenance`, `system.health`, `account.security` (portal mandatory, not
user-mutable), `communications.broadcast`; `support.incident` (016) and `statistics.wrapped` (017).

## Sending

```python
from portalab.capabilities.notifications import NOTIFY, CommunicationRequest, Users, declare_category

declare_category("media.new", "module:media", "media:category.new", default_channels=("portal",))
notify = capabilities.system_providers(NOTIFY)[0].provider
await notify.send(
    CommunicationRequest(
        category="media.new",
        template_key="media:new_title",          # rendered per recipient language (026); body = "new_title.body"
        audience=Users((user_id,)),               # or WithPermission(...), Role(...), AllAuthenticated()
        dedup_key=f"media:{item_id}:added",       # a retry never duplicates
        params={"title": item_title},             # plain values, never secrets
        subject_ref=f"media:{item_id}",           # coalescing key
        required_permission="media.read",         # re-checked for each recipient at delivery
        action_url=f"/media/{item_id}",           # in-portal route only
    ),
    caller=principal,                             # None/system for system sources
)
```

Audience authority: a caller may always notify themself; other audiences need
`notifications.send_to_audience` (and, for `WithPermission(p)`, the permission `p` itself); everyone needs
`notifications.broadcast`. Automations act under their author's authority.

## Delivery rules

- Channels = category defaults ∩ admin policy ∩ user preference; mandatory channels cannot be disabled
  (`422 notifications.mandatory_channel`); a stored choice is kept when a policy temporarily overrides it.
- Critical alerts bypass mutes **on the portal channel only** — never the e-mail opt-out, sound-off or
  reduced motion.
- Repeats about the same subject within `notifications.coalesceWindowSeconds` (default 120) merge into one
  item with a count; critical items are never merged.
- Lost permission ⇒ `suppressed(permission_lost)`; past `valid_until` ⇒ `suppressed(expired)`; no verified
  address ⇒ `suppressed(no_address)`. Each channel is independent.
- E-mail (disabled by default): outbox + job with exponential backoff and an attempt cap, then `failed`
  (visible to the Admin; content-free `notification.delivery_failed` event). Optional daily/weekly digest.

## Automation action `communication.produce`

Registered in the action registry for 019: params `category`, `template_key`,
`audience` (`{type: users|permission|role|all, …}`), `dedup_key` (from the trigger), optional `kind`,
`priority`, `params`, `action_url`. Permission `notifications.send_to_audience`; idempotent per dedup key.

## Maintenance reminders

A fixed system source driven by 006 `maintenance.*` events: J-1 and H-1 reminders per schedule version
(`notify.maintenance_reminders`), an alert when it starts, a corrective message when a maintenance already
announced is rescheduled or cancelled; a reminder evaluated after the start is `expired`, never sent late.
Replays never notify.

## API

- `GET /me/notifications` (`unread`, `kind`, `category`, `archived`, `cursor`), `GET …/unread-count`,
  `POST …/{id}/read|archive`, `POST …/read-all`, `DELETE …/{id}` — owner only.
- `GET|PUT /me/notification-preferences`, `GET /notifications/categories`.
- Admin (`notifications.manage`, audited): `GET /admin/notifications/status|deliveries` (metadata only),
  `PUT /admin/notifications/email`, `POST …/email/test`, `PUT …/categories/{key}`;
  `POST /admin/notifications/broadcast` (`notifications.broadcast`).

## Frontend

`/notifications` (center), `/settings/notifications` (preferences with `PolicyField`), the header bell
(004 slot, live unread count) and live toasts through 022's `NotificationArea` (user's position, duration,
style and sound preferences; critical alerts stay until acknowledged).
