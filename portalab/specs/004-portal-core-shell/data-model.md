# Data Model — Portal Core Shell

The shell is largely **stateless/derived**; it owns no durable business data. Preferences live in 020 config; module/plugin enablement lives in 020/023.

## NavigationContribution (declared in code/plugin manifest, validated, not a table)
`key` (stable, `<owner>.<name>`) · `owner` (`module:<id>|plugin:<id>`) · `kind` (`entry|command|related_link|crumb_parent`) · `label_key` (i18n) · `icon` (design-system id) · `route` or `action_id` · `group` · `order_hint` · `required_permission` · `resource_kind?` · `existence_sensitive?` · `visible_when` (declarative availability: module enabled, feature toggle key) · `schema_version`.
Closed schema; unknown fields rejected. Plugin contributions additionally constrained to the plugin's own namespace plus declared enrichment targets (`target_entry_key`).

## shell.contribution_errors (schema `shell`) — diagnostics only
`id` · `owner` · `key` · `reason` (`schema|duplicate|conflict|runtime`) · `first_seen_at` · `last_seen_at` · `count`. Pruned by retention. Feeds Observability; no user data.

## NavigationView (response, per user, computed)
`version` (etag derived from manifest+permissions hash) · `groups[]` → `entries[]` (`key,label_key,icon,route,badge?,state`) · `commands[]` · `generated_at`. Cached per `(principal, permission_epoch, module_epoch)`; epochs bumped by authz/config/plugin changes.

## User/Admin settings (declared into 020)
Global: `shell.navigation.layout` (groups, order overrides, pinned), `shell.navigation.allowUserOrdering`, `shell.shortcuts.defaults`. User: `shell.navigation.userOrder`, `shell.shortcuts`, `shell.sidebarCollapsed`.

## Events
Consumes: `permission.role_assigned|role_revoked|group_changed|permission_granted|permission_revoked|policy_changed` (003), `admin.module_toggled|plugin_toggled` (020), `plugin.state_changed`, `service.status_changed` (for badges). Emits (via 007): `navigation.contribution_rejected` (diagnostic). Dedup `(owner, key, reason, manifest_hash)`.

## Privacy
No personal data stored; navigation views are computed per request/session and not logged with identifiers.
