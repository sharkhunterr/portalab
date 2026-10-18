# Contract: plugin manifest, schema version 2

`plugin.toml`, validated by `modules/plugins/manifest/schema.py`. Every field of version 1 (spec 023) keeps
its meaning; version 1 files stay valid (`runtime` implied: `declarative` without `entry_point`,
`in_process` with one).

```toml
schema_version = 2
key = "moments"                      # [a-z][a-z0-9_]{1,30}
name = "Moments"
version = "1.0.0"
requires_portal = ">=0.30"
runtime = "confined"                 # "confined" (default) | "declarative"; "in_process" refused in v2
entry_point = "moments_plugin:register"
migrations = "migrations"

[capabilities]                       # the closed list; anything else blocks the version
storage = { quota_mb = 50 }
operations = true
permissions = ["view", "add"]
pages = false
slots = ["player.overlay", "player.button", "settings.member", "settings.admin"]
live = { topics = ["new"] }
events = { produces = ["moment_added"], consumes = ["user.deleted"] }
jobs = { names = ["purge_old"] }
notifications = false
search = false
moderation = false
privacy = true                       # required when personal_data.enabled
product_types = []
portal_data = { operations = ["media.get_item"], job_permissions = [] }
network = { hosts = [{ host = "api.example.org", port = 443, scheme = "https", private = false }] }

[[settings]]
name = "max_length"
type = "integer"
default = 140
description = "Longest moment, in characters"

[[settings]]
name = "api_key"
type = "string"
secret = true                        # kept by Portalab, never sent to the plugin
inject = { host = "api.example.org", header = "X-Api-Key" }
description = "Key for api.example.org"

[[routes]]                           # labels of what ctx.route registers (checked at registration)
path = "moments"
method = "GET"
permission = "view"
exposure = "read"

[[routes]]
path = "moments"
method = "POST"
permission = "add"
exposure = "committing"              # needs a describe handler; Portalab confirms with its summary
```

## Blocking findings at analysis

- unknown capability, slot, exposure label or block kind;
- `runtime = "in_process"` in a v2 manifest;
- `personal_data.enabled` without `privacy = true` and both privacy handlers registered;
- a `committing` route without a `describe` handler;
- a route, live topic, job, event or portal operation used at registration but not declared;
- a `portal_data` operation the catalog labels `committing`, `forbidden` or does not know;
- a host that is an IP literal of a private range without `private = true`, or a wildcard;
- a secret setting without `inject`, or injected toward an unlisted host;
- duplicate keys of routes, slots contributions, product types (023's resolution otherwise).
