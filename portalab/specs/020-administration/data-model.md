# Data Model — Administration & Configuration (schema `config`, `admin`)

## config.settings
`id` · `key` text · `scope` (`global|module|plugin|user`) · `scope_ref` text null (module name / plugin id / user id) · `value` jsonb (encrypted envelope when sensitive) · `schema_version` int · `updated_by` · `updated_at`. Unique (`key`, `scope`, `scope_ref`). User-scope rows carry PII class `preference` (tombstoned/erased with the user).

## config.policies
`id` · `key` · `mode` (`default|lock|bound`) · `bounds` jsonb null · `set_by` · `set_at` · `removed_at` null. Admin constraints on lower scopes; history kept.

## config.setting_history (append-only)
`id` · `key` · `scope` · `scope_ref` · `old_value_redacted` · `new_value_redacted` · `actor_id` · `changed_at` · `reason`. Mirrors audit for config (audit entry also written).

## admin.extension_toggles
`id` · `kind` (`module|plugin|connector|service|automation`) · `ref` · `enabled` · `changed_by` · `changed_at` · `reason`. State of record for enable/disable; data of disabled items is never deleted.

## admin.first_run
`id=1` · `completed_at` null · `completed_by` null. Guards the wizard.

## Registries (code)
`SettingDeclaration`, `SettingUpgrade` (stored-value migrations), `PanelProvider`, `RequiredActionProvider`.

## Events
`admin.config_changed`, `admin.policy_changed`, `admin.module_toggled|plugin_toggled|connector_toggled`, `admin.firstrun_completed`, `admin.import_performed|export_performed`. Dedup `(key, scope, scope_ref, change_seq)`.

## Implementation notes (2026-10-02)
- `config.settings.scope_ref` is `''` for global values (part of the unique key); user-scope rows hold the user
  id and are erased/exported by Administration's preference participants.
- `config.setting_history.scope_ref_hash`: user refs are SHA-256 hashed (append-only table, no PII); other
  scopes keep the module/plugin name.
- Allowed scopes per key: `global` always; `module`/`plugin` when declared at that scope; `user` when declared
  `user` or `user_overridable`. Policies (`default|lock|bound`) constrain the user tier only.
- Modules keep reading their config dataclasses; `app/config_bindings.py` refreshes them from the store at
  start-up and on `admin.config_changed` (Argon2 parameters apply after a restart).
- Contribution points live in `portalab.capabilities.administration` (panels, required actions, first-run steps,
  `identity.bootstrap`, `authz.plugin_permissions`, toggle hooks, `audit.status`, admin surfaces).

## Lifecycle / privacy
Settings are never hard-deleted for disabled plugins; user-scope values removed by the user's erasure participant; sensitive values encrypted; history redacted.
