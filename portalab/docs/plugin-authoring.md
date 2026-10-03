# Writing a Portalab plugin

A plugin is a directory (or a `.zip`) with `plugin.toml` at its root, optional code, SQL migrations and
image assets. The reference is `examples/plugins/hello/` — it contributes to every extension point.

```
hello/
├── plugin.toml
├── hello_plugin/__init__.py      # entry_point = "hello_plugin:register" (optional, Tier 2)
├── migrations/0001_init.sql      # run with the plugin's own role, in schema plugin_hello
└── assets/logo.png               # served at /api/v1/plugins/hello/assets/logo.png (images only)
```

## Manifest

```toml
key = "hello"                 # [a-z][a-z0-9_]{1,39}
name = "Hello"
version = "1.0.0"             # MAJOR.MINOR.PATCH
scope = "portal"              # or "user": every contribution is gated by plugin:<key>.use
maturity = "beta"             # experimental | beta | stable | deprecated (+ deprecation_notice)
requires_portal = ">=0.1"
requires_capabilities = [{ name = "identity.directory", range = ">=1.0" }]
requires_plugins = [{ key = "base", range = ">=1.0,<2" }]
extension_points = ["nav", "page", "widget"]          # only official points
permissions = [{ name = "view", description = "…" }]  # → plugin:hello.view (never reserved)
settings = [{ name = "greeting", type = "string", default = "Hello" }]   # → plugin.hello.greeting
entry_point = "hello_plugin:register"
migrations = "migrations"

[events]
produces = ["greeted"]          # → plugin.hello.greeted (validated by 007)
consumes = ["user.verified"]

[personal_data]
enabled = false                 # true requires erasure_participant = true

[ui]                            # declarative contributions (no code)
nav = [{ key = "home", label_key = "plugin.hello:nav.home", route = "/plugins/hello/main", permission = "plugin:hello.view" }]
# pages, widgets, notification_categories, statistics, themes …

[i18n.en."plugin.hello"]        # message catalogs under your own namespace
"nav.home" = "Hello"
```

`portalab plugin validate <dir>` checks the manifest and scans the code; `portalab plugin pack <dir>
<out.zip>` builds the package.

## Code (Tier 2)

Import **only** `portalab.sdk` and the standard-library allow-list (`json`, `re`, `datetime`, `typing`,
`dataclasses`, `asyncio`, …). The install-time scanner refuses process, network, FFI and dynamic-import
modules, Portalab internals, database engines, `eval`/`exec`/`open`.

```python
from portalab.sdk import PluginContext, WidgetDefinition

def register(ctx: PluginContext) -> None:
    async def count(principal, query, body):
        rows = await ctx.db.execute("SELECT count(*) AS n FROM greetings")
        return {"state": "available", "value": rows[0]["n"]}

    ctx.route("GET", "greetings/count", count, permission="plugin:hello.view")
```

Everything goes through `ctx`: `nav_entry`, `page`, `widget`, `action`, `search_provider`,
`calendar_source`, `statistics_pack`, `automation_action`, `event_type(…, automatable=True)`, `consume`,
`ai_tool`, `notification_category`, `theme`, `i18n_catalog`, `permission`, `setting`, `provide`,
`product_type`, `media_type`, `profile_section`, `discovery_shelf`, `connector`, `route` — and `ctx.db`
for your schema. The portal records each contribution and removes all of them when the plugin is
disabled or quarantined; your callables run behind the guard (timeout, error counting, quarantine).

## Rules

* **Isolation**: your role can only reach `plugin_<key>`; core data comes through capabilities.
* **Expand/contract**: an update may only add (tables, columns, indexes). Remove things in a later
  version, after the data no longer needs them.
* **Restarts**: new code (first enable, updates) is loaded at a restart; probation then watches it and
  rolls back on errors.
* **UI**: pages are declarative blocks; no JavaScript.

## Testing kit

`backend/tests/contract/plugins/kit.py` offers `check_manifest`, `check_contributions`,
`check_removal` and `check_guard` to run in your plugin's CI against a test portal.
