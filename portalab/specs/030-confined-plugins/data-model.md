# Data Model: Confined Extensions

All new tables live in the `plugins` schema (owned by `modules/plugins`, spec 023). UUIDv7 ids, `timestamptz`
UTC. Migrations `plugins_00NN` under `backend/migrations/plugins/versions/`.

## Changed: `plugins.plugins` (023)

| Column | Type | Notes |
|--------|------|-------|
| `runtime` | text | `declarative` (no code), `in_process` (023 code), `confined`; derived from the current version's manifest |
| `confinement` | jsonb | what the last child applied: `{landlock_abi, seccomp, rlimits, weak}`; null when not confined |
| `state` | text | 023's states plus `held_unconfined` (in-process code while `plugins.allowUnconfined` is false) and `held_confinement` (the kernel cannot confine and weak mode is off) |

## New: `plugins.grants`

What the Admin accepted for one version. One row per capability.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid | |
| `plugin_key` | text | FK `plugins.plugins.key` |
| `version` | text | |
| `capability` | text | closed list (`storage`, `operations`, `permissions`, `pages`, `slots`, `live`, `events`, `jobs`, `notifications`, `search`, `moderation`, `privacy`, `product_types`, `settings`, `network`, `portal_data`) |
| `parameters` | jsonb | e.g. `{hosts:[{host,port,scheme,private}]}`, `{operations:[…]}`, `{job_permissions:[…]}`, `{quota_mb:200}` |
| `granted_by` | uuid | admin user |
| `granted_at` | timestamptz | |
| `revoked_at` | timestamptz null | revocation takes effect at once (the host is told; calls needing it are refused) |

Unique (`plugin_key`, `version`, `capability`). A version can be enabled only when every capability its
manifest requests has a non-revoked grant.

## New: `plugins.attempts`

Forbidden or over-limit attempts, append-only (trigger), counted toward quarantine (023's `PluginGuard`).

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid | |
| `plugin_key` | text | |
| `version` | text | |
| `kind` | text | `denied_capability`, `denied_operation`, `denied_host`, `private_address`, `oversize`, `timeout`, `memory`, `crash`, `busy`, `storage_quota`, `rate`, `confinement` |
| `detail` | jsonb | bounded (≤ 2 KiB), sanitized: operation id, host, limit; never a payload or a secret |
| `occurred_at` | timestamptz | |

Index (`plugin_key`, `occurred_at desc`). Retention 90 days (025 purge job).

## New: `plugins.network_calls`

Hourly counters per plugin and host (the detail of each call goes to the structured log).

| Column | Type | Notes |
|--------|------|-------|
| `plugin_key` | text | PK part |
| `host` | text | PK part |
| `hour` | timestamptz | PK part |
| `calls`, `refused`, `bytes_in`, `bytes_out` | bigint | |

## New: `plugins.secret_settings`

| Column | Type | Notes |
|--------|------|-------|
| `plugin_key` | text | PK part |
| `name` | text | PK part |
| `ciphertext` | text | `SecretBox` token, context `plugins.setting:<key>:<name>` |
| `updated_by`, `updated_at` | uuid, timestamptz | |

The database role's password is a row of this table with the reserved name `__db` (context
`plugins.db:<key>`), never shown.

## New: `plugins.slot_settings`

Portal-wide order and visibility of contributions (Admin).

| Column | Type | Notes |
|--------|------|-------|
| `slot` | text | PK part |
| `contribution` | text | `<plugin>:<id>` or `core:<id>` (Portalab's own home sections and nav entries) |
| `position` | int null | |
| `hidden` | bool | |

## New: `plugins.confirmations`

Single-use tokens for committing plugin operations (R6).

| Column | Type | Notes |
|--------|------|-------|
| `token_hash` | bytea | PK, SHA-256 of the token |
| `user_id` | uuid | |
| `plugin_key`, `route` | text | |
| `body_hash` | bytea | SHA-256 of the canonical JSON body |
| `summary` | jsonb | what the dialog showed |
| `expires_at` | timestamptz | 5 min |
| `used_at` | timestamptz null | |

## User setting (020/022)

`ui.hiddenContributions`: list of `<plugin>:<id>` a member hid, plus `ui.coreOrder` per slot when they
restored or changed Portalab's order.

## Settings (administration)

`plugins.allowUnconfined` (bool; true on an upgraded install with in-process code plugins, false otherwise),
`plugins.allowWeakConfinement` (bool, false), `plugins.hookTimeoutSeconds` (5), `plugins.jobTimeoutSeconds`
(60), `plugins.concurrentCalls` (8), `plugins.memoryMb` (384), `plugins.storageQuotaMb` (200),
`security.egressAllowList` (bool, false on upgrade), `security.egressHosts` (list), `security.moduleRoles`
(bool, false), `audit.offsite` (`{syslog:{host,port,tls}, file:{path}}`).

## Manifest v2 (excerpt; full contract in contracts/manifest-v2.md)

```toml
schema_version = 2
key = "forum"
runtime = "confined"            # default for v2
entry_point = "forum_plugin:register"

[capabilities]
storage = { quota_mb = 100 }
operations = true
permissions = ["read", "post", "moderate"]
pages = true
slots = ["nav", "page", "search.kind", "notification.kind"]
notifications = true
search = true
events = { produces = ["topic_posted"], consumes = ["user.deleted"] }
privacy = true
portal_data = { operations = ["identity.get_profile"] }
network = { hosts = [] }
```

## State transitions

```text
installed ─► reviewed (all grants) ─► enabled ─► running (child up)
                    ▲                    │  ├─► quarantined (attempts ≥ threshold) ─► enabled (Admin) / disabled
                    │                    │  └─► held_confinement (kernel cannot confine, weak mode off)
 update needing more capabilities ───────┘     held_unconfined (in-process code, allowUnconfined off)
```
