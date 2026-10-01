# Contracts — Extensibility

## Public SDK `portalab.sdk` (the only import surface for plugins)
`PluginContext` passed to `register(ctx)`: tracked registration helpers —
`ctx.nav.entry(...)` (004) · `ctx.pages.page(PageDefinition)` · `ctx.widgets.register(defn, provider)` (009) · `ctx.actions.register(ActionDef)` (004/008) · `ctx.search.provider(...)` (008) · `ctx.calendar.source(...)` (011) · `ctx.stats.pack(...)` (017) · `ctx.automation.action_type(...)`/`trigger_events(...)` (019) · `ctx.ai.tool(...)` (018) · `ctx.notify.category(...)` (010) · `ctx.themes.register(...)` (022) · `ctx.i18n.catalog(...)` (026) · `ctx.permissions.declare(...)` (003, namespaced) · `ctx.settings.declare(...)` (020) · `ctx.events.type(...)`/`ctx.events.consume(...)` (007) · `ctx.capabilities.provide|consume(...)` (001) · `ctx.products.type(...)` (015) · `ctx.media.type(...)` (024) · `ctx.community.profile_section(...)` (012) · `ctx.connectors.register(...)` (005) · `ctx.db` (`PluginDb`, role-bound session) · `ctx.jobs` (worker-only handlers) · `ctx.logger`.
Everything registered is recorded in the contribution ledger and removed on disable/quarantine.
`PluginGuard` wraps every plugin-supplied callable (timeouts, exceptions, counters).
`ExtensionActivation` (consumed by 015): `activate_for_user(product_ref, user)`, `deactivate_for_user`, `status(product_ref, user) -> active|needs_configuration|failed|incompatible` (grants/revokes `plugin:<key>.use` via 003).
`ModuleRegistry`: `ModuleDescriptor{key, requires, provides}`; `enable/disable` with dependents check (first-party feature lifecycle).

## Manifest (`plugin.toml`, validated by JSON Schema)
`key, name, version, scope, maturity, requires_portal, requires_capabilities[], requires_plugins[], provides{…}, permissions[], settings[], events{produces[], consumes[]}, personal_data{enabled, classes[]}, migrations, i18n, ui{pages[], widgets[], nav[], …}, entry_point?`.

## HTTP (`/api/v1`)
| Path | Permission |
|---|---|
| GET `/admin/plugins` · GET `/admin/plugins/{key}` (state, versions, contributions, errors, deps, maturity) | `plugins.read` |
| GET `/admin/plugins/discovery` (available packages + Marketplace plugin products + compatibility preview) | `plugins.read` |
| POST `/admin/plugins/install` (upload or `source=local:<file>`) → review object · POST `…/{key}/approve` (consent record) | `plugins.manage` (sensitive, audited) |
| POST `/admin/plugins/{key}/enable|disable|archive` | `plugins.manage` (audited; cascade with confirmation) |
| PUT `/admin/plugins/{key}/settings` | `plugins.manage` (audited; via 020) |
| POST `/admin/plugins/{key}/update` (stage) · `/update/confirm-restart` · `/rollback` | `plugins.manage` (sensitive) |
| POST `/admin/plugins/{key}/purge` `{export: bool}` | `plugins.purge` (sensitive, `ConfirmationService`, audited) |
| GET `/admin/plugins/{key}/diagnostics` (contribution ledger, conflicts, error stats) | `plugins.read` |
| `/api/v1/plugins/{key}/…` | plugin-declared routes: default-deny, per-route permission from manifest, `PluginGuard`, rate limits |
| GET `/plugins/{key}/assets/…` | authenticated; images/static only, strict CSP |
| GET/PUT `/admin/modules` · POST `/admin/modules/{key}/enable|disable` | `modules.manage` (020 toggles + dependency resolver) |
CLI: `portalab plugin validate <pkg>` · `pack` · `install` · `enable` · `disable` · `update` · `purge`.
Problem codes: `plugin.incompatible`, `plugin.dependency_missing`, `plugin.dependency_cycle`, `plugin.has_dependents`, `plugin.invalid_manifest`, `plugin.requires_restart`, `plugin.quarantined`.

## Frontend
Admin plugin manager (list, discovery, install wizard with review/consent, enable/disable with cascade preview, settings, update/rollback, archive/purge with export, diagnostics, dependency graph, maturity badges); runtime **page renderer** for `PageDefinition` blocks (design-system only); shell integrations via 004/009 registries.
