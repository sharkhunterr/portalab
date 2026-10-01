# Contract — Bootstrap Settings vs Administration Configuration

CD-011: **Administration (020) owns the configuration system** (Global → Module → Plugin → User). The kernel must
not become a second one. The split is strict:

## Bootstrap settings (environment/files only — needed before the DB is usable)

| Setting | Purpose | Notes |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection | secret-bearing ⇒ supports `DATABASE_URL_FILE` |
| `SECRET_KEY_FILE` | application key for encrypting stored credentials & signing | file path; never an inline value in compose files committed to Git |
| `BIND_HOST` / `BIND_PORT` | HTTP listener | defaults safe for containers |
| `LOG_LEVEL` | bootstrap log verbosity | runtime log policy later via Administration |
| `RUN_MODE` | `serve` or `worker` entrypoint | CLI argument preferred |

Rules: validated at start (fail fast with a clear error); secrets only through `*_FILE`; no business or UX
setting is ever read from the environment.

## Everything else → Administration configuration

A module/plugin **declares** its settings; Administration stores, resolves and audits them.

```
declare_setting(
  scope = Global | Module | Plugin | User,
  key   = "<module>.<name>",          # e.g. "i18n.defaultLanguage"
  schema = <validated type>, default = <value>,
  user_overridable = bool, sensitive = bool, version = int,
)
```
- Effective value = hierarchy resolution; admin policy may constrain user preferences while the underlying
  preference is retained (CD-011/016).
- Sensitive settings are stored encrypted and write-only in the API.
- Changes emit `admin.config_changed` (event owned by 007's model) and are audited (CD-013).
- The declaration API lands with the *Configuration* step; until then modules use code defaults only.
