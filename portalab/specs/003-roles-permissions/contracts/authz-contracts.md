# Contracts — Authorization

## `authorize()` (consumed by every module, AI, automations, plugins)
```
authorize(principal, permission_key, resource=Resource(kind,id,owner_id?,module?,service_id?,plugin_id?), *, context=None)
  -> Decision{allowed: bool, reason, scope_matched, requires_confirmation: bool}
require(...)  # raises Forbidden/NotFound per existence-leak policy
```
Rules: deny by default · explicit deny wins · union of role+group grants · scope matched structurally · Admin role = all *enabled* permissions minus explicit denies · `principal.channel != user` never widens rights · evaluation reads current DB state (no cross-request cache).

## `declare_permission(key, description, sensitive=False, reserved=False, requires_confirmation=False, default_roles=[...])`
Called at import time by core/modules/plugins; idempotent upsert; reserved ⇒ Admin only.

## `authz.admin_authority` capability (consumed by identity)
`grant_first_admin(user_id)` (only when none) · `transfer_admin(from_user, to_user, actor)` atomic · `current_admin()`.

## `AuditSink` port
`record(action, actor, resource, decision, result, context)` — append-only; failure to audit a **sensitive** action fails the action (fail closed); failure for non-sensitive records is logged and counted.

## `ConfirmationService`
`issue(principal, permission, resource, payload) -> token` · `consume(token, principal, permission, resource, payload) -> bool` (single use, short TTL).

## HTTP (`/api/v1`)
| Path | Permission |
|---|---|
| GET `/permissions` (catalog) | `users.roles.manage` |
| GET/POST/PATCH `/roles`, `/groups`, grants | `users.roles.manage` (sensitive, audited; reserved perms refused for non-Admin roles) |
| POST/DELETE `/users/{id}/roles`, `/users/{id}/groups` | `users.roles.manage` |
| GET `/me/permissions` | self (effective set for UI hints; never the authority) |
Error codes: `authz.forbidden`, `authz.reserved_permission`, `authz.sole_admin_protected`, `authz.confirmation_required`.
