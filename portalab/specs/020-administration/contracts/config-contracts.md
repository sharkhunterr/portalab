# Contracts — Configuration & Administration

## `declare_setting` (kernel contract from 001, persisted here)
`declare_setting(key, scope_levels, schema, default, user_overridable, sensitive, version, upgrade=None)`.

## `ConfigService` (capability `admin.config`)
`get(key, *, user=None, module=None, plugin=None) -> EffectiveValue{value, source_scope, locked: bool}` · `set(key, value, scope, scope_ref, actor)` · `validate(changes) -> Preview{diff, warnings, errors}` · `effective_for_user(user_id) -> dict` · `UserPreferenceReader` (implements the i18n/identity read ports).

## Provider registries
`PanelProvider.panel(principal) -> PanelResult{state, data}` · `RequiredActionProvider.items(principal) -> [Action{id,title,impact,criticality,since,link}]`.

## HTTP (`/api/v1`)
| Path | Permission |
|---|---|
| GET `/admin/overview` | `audit.read`-independent: `security.manage` or per-panel permission; panels filtered |
| GET `/admin/config`, POST `/admin/config/validate`, PUT `/admin/config` | `configuration.manage` (sensitive keys: write-only) |
| GET/PUT `/me/preferences` | `users.self.manage` (user-tier settings only, bounded by policy) |
| POST `/admin/policies`, DELETE `/admin/policies/{id}` | `configuration.manage` (sensitive) |
| POST `/admin/toggles/{kind}/{ref}` | `modules.manage` / `plugins.manage` / `connectors.manage` (sensitive, audited) |
| POST `/admin/config/export`, `/import` | `configuration.manage` (sensitive) |
| GET/POST `/admin/first-run` | public until the sole Admin exists; once reopened (POST `/admin/first-run/reopen`, `configuration.manage`, audited) it runs as that Admin; 410 when completed |
| GET `/admin/surfaces` | `users.self.manage` (lists only the surfaces the caller may use) |
| GET `/admin/overview` | `users.self.manage`; panels/actions filtered by their own permissions |
`PUT /admin/config` accepts `Idempotency-Key`; a retry with the same key applies nothing. CLI: `portalab backup --output DIR`, `portalab restore --input DIR --yes`, `portalab migrate --status`.
