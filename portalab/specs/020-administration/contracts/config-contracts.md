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
| POST `/admin/first-run` | only before completion; creates sole Admin via `IdentityBootstrap` |
