# Extensibility — plugins, discovery, feature lifecycle (spec 023)

The `plugins` module owns the extension registry and lifecycle. The core runs unchanged with
`plugins.enabled = false` or with no plugin installed: nothing in `core`, `capabilities` or `sdk` imports
plugins (import-linter contract `core-no-plugins`).

## Tiers and trust (R1–R3)

| Tier | What | Who | Isolation |
|---|---|---|---|
| 1 — declarative | manifest + data only: nav entries, pages, template widgets, statistics packs, themes, message catalogs, notification categories, permissions, settings, event types | Admin | no code runs |
| 2 — trusted code | a Python package loaded in the app and the worker, contributing through `PluginContext` | Admin only, after review | import scan, guarded hooks, own schema/role, quarantine |
| 3 — sandboxed | out-of-process plugins over HTTP | future | — |

Only the single Admin installs and enables plugins. Installing shows a **review** (permissions, extension
points, events, personal data, capabilities, own schema, code or not, SHA-256) that must be approved
before enabling (`plugins.requireReview`). Marketplace *plugin* products reference a plugin the Admin
installed; acquiring one grants `plugin:<key>.use` to that member (`ExtensionActivation`, 015).

**In-process Python plugins are trusted code.** The import scanner, the guard and role isolation limit the
blast radius; they are not a sandbox.

## Lifecycle

`installed → (needs_configuration) → enabled ⇄ disabled → archived`, plus `incompatible`, `quarantined`,
`update_pending` and `update_failed`. Every transition is permissioned (`plugins.manage`), audited and
emits `plugin.<event>` and `plugin.state_changed` (`plugin_id`, `plugin`, `from_state`, `state`,
`reason`, `seq`; dedup `(plugin, seq)`).

* **Enable** checks the approval, compatibility (portal version, required capability versions — refused
  with named reasons, state `incompatible`), dependencies (missing, incompatible range, disabled, cycle),
  the package checksum (a tampered package is refused), then provisions schema `plugin_<key>` and role
  `plugin_<key>`, runs the plugin's migrations with that role and registers the contributions. Declarative
  ones are live at once; code is loaded at the next (graceful) restart (`needs_restart`) — Python cannot
  unload modules.
* **Disable** with enabled dependents is refused (`plugin.has_dependents`) unless the Admin confirms the
  cascade. Disable and quarantine **remove every contribution** and never delete data.
* **Purge** (`plugins.purge`, confirmation, audit) is the only way to delete a plugin's data: optional JSON
  export, then the schema and role are dropped.

## Clean removal by construction (R7)

Plugins register only through `PluginContext`, which owner-tags each contribution `plugin:<key>` and
records it in the contribution ledger (`plugins.contributions`). Removal sweeps **every** registry with
`unregister(owner)`: navigation, pages, widgets, palette actions and search providers, calendar sources,
statistics packs, automation actions, AI tools, notification categories, permissions, settings, event
types and consumers, capabilities, product types, media types, profile sections, discovery shelves,
connectors, routes, observability — and, through capability ports, the message catalogs (026) and themes
(022). The conformance sweep (`tests/integration/plugins/test_clean_removal.py`) proves every registry is
empty for the owner after disable and quarantine, and that re-enabling restores everything.

Conflicts (a slot already owned, e.g. a single-provider capability) are recorded as `conflict` in the
ledger and shown in diagnostics; plugins load in dependency order, ties by
`(plugins.contributionPriority, key)`.

## Isolation and failure handling (R3)

* **Data**: each plugin owns schema `plugin_<key>` and a role with rights on that schema only and a
  `statement_timeout`; `ctx.db` runs `SET LOCAL ROLE`, so core tables and other plugins' schemas are
  unreachable. Core data is available only through capabilities. No foreign keys to core tables.
* **Failures**: every plugin callable (routes, widget providers, search providers, calendar sources,
  automation actions, AI tools, event handlers, profile sections, shelves, loading) runs inside the
  **PluginGuard** — timeout (`plugins.hookTimeoutSeconds`), exception capture (the request fails alone
  with `plugin.hook_failed`, no stack trace), counters in `plugins.error_stats`, a per-plugin rate limit,
  and **quarantine** at `plugins.errorThreshold` errors in 10 minutes (contributions removed, data kept,
  Admins notified via `plugins.quarantined`). A plugin failing at startup is quarantined; the portal
  still starts. Event handlers are worker consumers.

## Updates and rollback (R10)

`POST /admin/plugins/{key}/update` stages the new version beside the current one, checks compatibility,
runs **expand-only** migrations (a `DROP`, `RENAME`, `TRUNCATE` or `DELETE` step is refused — destructive
changes come in a later version) and marks `update_pending`. After the restart
(`…/update/confirm-restart`) the new version runs under **probation**
(`plugins.updateProbationMinutes`); errors during probation, a load failure or a failed migration roll
back to the previous package automatically (`plugin.update_failed`, `plugin.rolled_back`) with the data
intact. Every version stays recorded (`plugins.versions`, append-only) and on disk.

## Discovery and first-party modules (R15)

Discovery lists the packages dropped into `plugins/available/` with their maturity
(`experimental → beta → stable → deprecated`), deprecation notice and a compatibility and dependency
preview — nothing is downloaded automatically. First-party modules have descriptors (`requires`); the
module manager (`modules.manage`) enables/disables them through the 020 toggles, refusing to disable a
module others need (unless cascaded) and removing its contributions with the same sweep; the 020
`ToggleHook` checks dependencies before enabling a module or a plugin.

## UI extensions (R12)

Plugin pages are **declarative**: Markdown (sanitized by the 011 renderer), stat/list/table/chart blocks
filled from the plugin's own routes (typed states), and forms generated from a JSON Schema posting to a
plugin action. The SPA renders them with design-system components (`/plugins/<key>/<page>`); no plugin
JavaScript runs. Plugin routes live under `/api/v1/plugins/<key>/…`: default-deny, each declared with a
permission, rate-limited and guarded. Assets (`/api/v1/plugins/<key>/assets/…`) are images only with a
strict CSP.

## API

| Path | Access |
|---|---|
| `GET /api/v1/admin/plugins` · `GET …/{key}` · `GET …/{key}/diagnostics` · `GET …/discovery` | `plugins.read` |
| `POST /api/v1/admin/plugins/install` (`{package}` from `plugins/available`) · `POST …/upload?filename=` (raw zip) | `plugins.manage` |
| `POST /api/v1/admin/plugins/{key}/approve|enable|disable|archive` · `PUT …/settings` | `plugins.manage` (cascade confirmed) |
| `POST /api/v1/admin/plugins/{key}/update` · `…/update/confirm-restart` · `…/rollback` | `plugins.manage` |
| `POST /api/v1/admin/plugins/{key}/purge` | `plugins.purge` + confirmation |
| `GET /api/v1/admin/modules` · `PUT /api/v1/admin/modules` · `POST …/{key}/enable|disable` | `modules.manage` |
| `GET /api/v1/plugins/pages` · `GET /api/v1/plugins/{key}/pages/{page}` · `GET …/assets/{path}` | signed-in member + page permission |
| `GET|POST /api/v1/plugins/{key}/{path}` | the route's declared permission |

CLI: `portalab plugin validate|pack|install [--approve]|enable|disable [--cascade]|update|purge [--no-export]`.

## Recorded deviations (T037)

* Plugin migrations are ordered SQL files run with the plugin role and tracked in the plugin's schema,
  not an Alembic branch per plugin (same isolation, simpler packaging).
* Lifecycle event payloads carry `plugin` instead of `plugin_key` (keys containing `key` are treated as
  secret-looking by the 007 payload checks).
* The upload route takes a raw `application/zip` body (`?filename=`); multipart is not a dependency.
* Asset URLs live under `/api/v1/plugins/<key>/assets/` (the SPA owns `/plugins/<key>/<page>`).
* In a running process, switching plugin code versions forgets the cached modules of the old version;
  objects created by the old code may live on until the restart that completes an update.
* Plugin-provided capabilities are declared on first use under `plugin.<key>.*` (no spec removal on
  disable; providers are removed).
* Open product confirmations (OQ-110..114 defaults): Admin-only trust model, tiers 1–2 only, restart to
  load code, no plugin-defined extension points, data kept until an explicit purge.

## Deployment

* Packages live under `${DATA_DIR}/plugins/{available,installed}` (the data volume: back it up).
* Per-plugin roles need a database user with `CREATEROLE` (or the database owner).
* Restart `serve` and `worker` gracefully after enabling a code plugin or confirming an update; both load
  enabled plugins at startup (dependencies first) and quarantine any that fails.

## Visual experience hooks (spec 027)

Plugins place their pages in a navigation section (`[[ui.sections]]` + `section = "plugin-<key>"` on `ui.nav`
entries, or `ctx.nav_section()` / `ctx.nav_entry(..., group=, topic=)`), build pages with the design-system kit
(`PageHeader`, cards, tiles, empty states…) and may ship themes using the v2 vocabulary — layout, motion and sound
profiles included — under the same validation, accessibility floor and enablement rules as other themes.
