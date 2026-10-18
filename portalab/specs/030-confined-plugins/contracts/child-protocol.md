# Contract: Portalab ↔ confined plugin process

Transport: the child's stdin (parent → child) and stdout (child → parent), one UTF-8 JSON object per line,
at most 1 MiB per line (a longer line is an `oversize` attempt and the child is restarted). stderr is read
by the parent, truncated to 4 KiB per line, logged with the plugin key. Every message has `t` (type); calls
carry `id` (integer, unique per direction).

## Start

| Direction | Message | Content |
|-----------|---------|---------|
| child → parent | `confined` | `{landlock_abi, seccomp: true, rlimits: {...}, weak: false}` — sent after confinement, before any plugin code; the parent refuses (and records `confinement`) a child that applied less than required |
| parent → child | `hello` | `{plugin: {key, version}, entry_point, settings: {non-secret}, grants: [capability…], sdk: "2.0"}` |
| child → parent | `registered` | `{contributions: {...declarative data...}, handlers: [{hid, kind, ...}]}` — what `register(ctx)` recorded; handler kinds: `route`, `describe`, `consumer`, `widget`, `search`, `action`, `product_hook`, `job`, `slot_data`, `privacy_export`, `privacy_erase`, `presence` |
| child → parent | `ready` | — |

## Parent calls a handler

```json
{"t": "call", "id": 7, "hid": 3, "deadline_ms": 5000,
 "args": {"member": {"id": "…", "name": "…", "locale": "fr", "permissions": ["plugin:forum.post"]},
          "query": {}, "body": {"title": "…"}}}
{"t": "result", "id": 7, "ok": true, "value": {...}}
{"t": "result", "id": 7, "ok": false, "error": {"type": "ValueError", "message": "…"}}
```

A result after the deadline is dropped. `error.message` is truncated to 300 characters and never shown to
members (they get `plugin.hook_failed`).

## Child asks a capability

```json
{"t": "ask", "id": 12, "cap": "db.execute", "args": {"sql": "SELECT …", "params": [1]}}
{"t": "answer", "id": 12, "ok": true, "value": {"rows": [...], "rowcount": 1}}
{"t": "answer", "id": 12, "ok": false, "error": {"code": "denied", "message": "network is not granted"}}
```

| `cap` | Needs grant | Arguments → value |
|-------|-------------|-------------------|
| `db.execute` | `storage` | `{sql, params}` → `{rows, rowcount}` (one statement, R5) |
| `portal.call` | `portal_data` | `{operation, params, as: "member"\|"plugin", member_id?}` → `{status, body}` |
| `http.request` | `network` | `{method, url, headers, body_b64?, timeout_s}` → `{status, headers, body_b64}` |
| `live.publish` | `live` | `{topic, payload, audience: {users?, permission?}, author?}` → `{}` |
| `notify` | `notifications` | `{users, category, title, body, link}` → `{sent}` |
| `events.emit` | `events` | `{type, payload, occurred_at?}` → `{id}` |
| `jobs.enqueue` | `jobs` | `{job, payload, run_at?}` → `{id}` |
| `settings.get` | — | `{}` → non-secret settings |
| `log` | — | `{level, message}` → `{}` (bounded, rate-limited) |

An ask whose capability is not granted, revoked, or whose parameters fall outside the grant answers
`{code: "denied"}` and records an attempt.

## Liveness

Parent sends `{"t":"ping","n":5}` every 10 s; the child answers `{"t":"pong","n":5}`; three missed pongs →
the child is killed and restarted (a `crash` attempt). The parent sends `{"t":"stop"}` then kills after 2 s.
