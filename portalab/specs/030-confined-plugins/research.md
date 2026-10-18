# Research: Confined Extensions

Grounded in the code as built on the POC (`impl/029-interfaces-catalog`: spec 023's `modules/plugins`, `sdk`,
`plugins_runtime`, `PluginGuard`, `PluginStorage`; 028's sandbox; 029's exposure catalog). Kernel probed on
the development host: Linux 7.0, Landlock ABI 8, seccomp filters available, Yama ptrace scope 1.

## R1 — One process per plugin, the same SDK

- **Decision**: a confined plugin's code runs in a child process of its own (`python -I -m
  portalab.plugins_runtime.confined.child`), started and supervised by the Portalab process that needs it
  (`serve` for routes, pages, widgets, search, slots; `worker` for events and jobs). The child imports the
  plugin's entry point and calls its `register(ctx)` with a **recording context** that has 023's exact SDK
  surface (`portalab.sdk.PluginContext`): what a plugin registers is sent to the parent as data (its
  declarative contributions) plus handler ids; the parent installs **proxies** in 023's registries (routes,
  consumers, widget and search providers, actions, product type hooks, jobs) that call the child.
- **Rationale**: 023's registries, admin, lifecycle, quarantine and pages keep working untouched; a 023
  code plugin migrates by declaring `runtime = "confined"` (R12) without rewriting its code, as long as it
  only used the SDK. The Python runtime is already in the image (no new language, no new dependency).
- **Alternatives**: WebAssembly (wasmtime) — strongest isolation but a new dependency, no Python plugins
  without a heavy toolchain, every 023 plugin rewritten; containers per plugin — needs the Docker socket
  (a privilege far worse than the risk it removes); in-process with a stricter import guard — what #142
  shows is not confinement.

## R2 — Confinement by the kernel, unprivileged

- **Decision**: before importing any plugin code, the child confines itself, irreversibly:
  1. `prctl(PR_SET_NO_NEW_PRIVS)`; an **empty environment** (only `LANG`, `PYTHONHASHSEED`), working
     directory its private scratch folder, every descriptor closed except its three pipes;
  2. **rlimits**: address space (default 384 MiB), file size 16 MiB, open files 64, core 0, CPU seconds as a
     backstop (per-call time is the parent's, R3);
  3. **Landlock** (ABI ≥ 4 required): file access only to Python's own folders and the portalab package
     (read and execute), the plugin's installed version (read), its scratch folder (read, write), `/dev/null`
     and `/dev/urandom`; **every TCP bind and connect denied**; with ABI ≥ 6, abstract Unix sockets and
     signals scoped to itself;
  4. **seccomp** (a BPF filter built with `ctypes`, no library): `socket` refused (only `socketpair`, which
     asyncio needs, stays), no `execve`/`execveat`, `fork`/`vfork`, `clone` without `CLONE_THREAD`, `clone3`
     (→ `ENOSYS`, glibc falls back to `clone`), `ptrace`, `process_vm_readv/writev`, `kill`/`tgkill` except
     to itself, `tkill`, `pidfd_*`, `mount`, `umount2`, `pivot_root`, `chroot`, `setns`, `unshare`, `bpf`,
     `perf_event_open`, `keyctl`, `add_key`, `request_key`, `userfaultfd`, `io_uring_*` (which bypasses
     seccomp), module and `kexec` calls.
  The child reports what it applied (`landlock_abi`, `seccomp`, `rlimits`) in its first message; the parent
  refuses a child that did not apply everything. **Where the kernel cannot** (no Landlock ABI ≥ 4, seccomp
  refused), confined plugins are **held** unless the Admin enabled `plugins.allowWeakConfinement`, shown
  with a permanent warning (spec clarification, FR-001).
- **Rationale**: unprivileged (works as the image's user 10001 inside Docker's default seccomp profile, which
  allows `landlock_*` and `seccomp`), no setuid helper, no new package; the process cannot reach the
  database (no socket), the secrets (no file of the portal, no `/proc`, no environment), the network, other
  plugins (no shared folder) or the server (no signal, no ptrace, no exec).
- **Alternatives**: user and network namespaces (`unshare -rn`) — refused by Docker's default seccomp
  profile and by Ubuntu's AppArmor userns restriction; a distinct Unix user per plugin — needs root to switch.

## R3 — The protocol: JSON lines over pipes, both ways

- **Decision**: one message per line on stdin/stdout (UTF-8 JSON, at most 1 MiB, larger refused and
  counted); messages `hello`, `ready`, `registered`, `call`/`result` (the parent calls a handler), `ask`/
  `answer` (the child asks a capability), `ping`/`pong`, `log` (bounded, sanitized). Every `call` has the
  parent's deadline (`plugins.hookTimeoutSeconds`, default 5 s; jobs 60 s); a late answer is dropped and the
  call fails cleanly (`plugin.hook_failed`). stderr is read, truncated and logged with the plugin's key.
  At most `plugins.concurrentCalls` (default 8) calls in flight per plugin; beyond, `plugin.busy` (429).
- **Rationale**: no socket needed (R2), trivially framed, testable with a fake child; the parent stays the
  only one that talks to anything.

## R4 — Supervision, limits and quarantine

- **Decision**: a `ConfinedHost` per plugin in each process: lazy start on first need (and at boot for
  enabled plugins with consumers or jobs in the worker), heartbeat every 10 s, restart with backoff (1 s,
  5 s, 30 s); crashes, timeouts, refused capability requests (`denied`), oversize messages and limit breaches
  are **attempts** recorded in `plugins.attempts` and counted by 023's `PluginGuard` toward quarantine
  (`plugins.errorThreshold`). On quarantine the child is stopped, its live channels closed, contributions
  withdrawn (023), the Admin notified.
- **Rationale**: reuses 023's guard, counters and quarantine as built.

## R5 — Storage: a login role per plugin, statements run by Portalab

- **Decision**: 023 already provisions `plugin_<key>` (schema + role without rights on core schemas). For a
  confined plugin the role gets `LOGIN`, a random password kept by Portalab encrypted (`SecretBox`, context
  `plugins.db:<key>`), `CONNECTION LIMIT 3`; the parent opens a tiny asyncpg pool **as that role** and runs
  each `ctx.db.execute(sql, params)` as **one** prepared statement (asyncpg's extended protocol refuses
  several), in its own transaction with `statement_timeout` (default 2 s), results capped (1 000 rows,
  1 MiB). A statement whose first keyword is a transaction or session command (`BEGIN`, `COMMIT`,
  `ROLLBACK`, `SET`, `RESET`, `LISTEN`, `NOTIFY`, `COPY`, `DO`, `LOAD`, `ALTER SYSTEM`) is refused. **Quota**
  (`plugins.storageQuotaMb`, default 200): the schema's size is measured every 30 s and after migrations;
  over it, statements run in `BEGIN READ ONLY` transactions (PostgreSQL refuses switching to read-write
  after the first query) and the Admin is told.
- **Rationale**: logging in as the plugin role makes `RESET ROLE` harmless (it returns to the plugin role);
  the role has no membership, no rights outside its schema, cannot create extensions, untrusted languages,
  or read server files; `pg_stat_activity` hides other roles' queries.
- **Alternatives**: keep 023's `SET LOCAL ROLE` on Portalab's connection — a plugin statement could
  `RESET ROLE` or `set_config('role', …)` back to Portalab's role.

## R6 — Operations, permissions and Portalab's confirmations

- **Decision**: a plugin route (023 `ctx.route`) gains an **exposure label** (`read`, `action`,
  `committing`); unlabelled = `action` for 023 compatibility, `committing` requires a `describe` handler.
  Portalab authenticates, checks the permission, rate-limits, then calls the child with only
  `{member: {id, name, locale, permissions-of-the-plugin}, query, body}`. A **committing** call without a
  valid `confirmation` gets 409 `plugin.confirmation_required` with a token and the **summary** the
  plugin's `describe` handler returned (title, lines, amount) — drawn by Portalab's own `ConfirmDialog`,
  never by the plugin; the front resends with the token (single use, 5 min, bound to member, plugin, route
  and body hash).
- **Rationale**: the same pattern as administration's `authz.confirmation_required`; the exact content is
  what is confirmed, since the body hash binds it.

## R7 — Portal data through the exposure catalog

- **Decision**: `ctx.portal.call(operation, params)` lets a plugin call a portal API operation by its
  operation id: allowed only if the catalog labels it `read` or `action` **and** the Admin accepted it at
  review (`portal_operations` in the manifest); `committing`, `forbidden` and unlabelled ones are refused
  (`denied`, counted). The parent runs it **in-process through the ASGI app** as the acting member: an
  internal scope key (`portalab.acting_principal`, impossible to set from HTTP) that the authentication
  dependency honours; responses capped at 1 MiB. Jobs and event handlers have no member: they may call only
  `read` operations, as a **plugin principal** holding exactly the permissions listed in
  `job_permissions` and accepted at review.
- **Rationale**: one catalog for every caller (029's purpose), the same authorization code, no new data
  access path.

## R8 — Network through Portalab, to listed hosts only

- **Decision**: `ctx.http.request(...)` → the parent checks scheme (`https`, `http` only if listed as such),
  host and port against the hosts accepted at review, resolves the name and **refuses private, loopback,
  link-local, multicast and reserved addresses** unless the host is listed with `private = true`; connects to
  the resolved address (no second resolution), no redirects to other hosts, 10 s, 5 MiB, 60 calls/min per
  plugin; **secret settings** are added by Portalab where the manifest says (`inject = {header|query,
  setting}`), never handed to the child; every call is recorded (host, method, status, bytes, duration) and
  counted per hour in `plugins.network_calls`; refused calls are attempts.
- **Rationale**: the plugin has no socket (R2), so this is the only way out; SSRF and DNS-rebinding guarded.

## R9 — Settings and secrets

- **Decision**: 023's `settings` gain `secret = true`: stored encrypted (`SecretBox`, context
  `plugins.setting:<key>:<name>`), shown write-only in the administration (« set », « replace », « clear »),
  never sent to the child, never logged (registered with the redaction filter), used only by R8's
  injection. Non-secret settings are sent in `hello` and on change.

## R10 — Pages and slots drawn by Portalab

- **Decision**: 023's declarative blocks (`markdown`, `stat`, `list`, `table`, `chart`, `form`) are widened
  with `actions` (buttons calling the plugin's operations), `cards` (titles, people or products as Portalab's
  cards), `thread` (messages with author, time, replies) and `live` (a block refreshed by the plugin's live
  topic). **Slots** (closed list, versioned): `nav`, `page`, `home.section`, `media.actions`,
  `media.panel`, `person.panel`, `profile.section`, `player.overlay`, `player.button`, `settings.member`,
  `settings.admin`, `dashboard.widget`, `search.kind`, `notification.kind`. A slot contribution names its
  data operation; Portalab calls it with the context (title id, time window for the player…) and draws the
  blocks with its own components. A custom visual is a 028 element (sandboxed, no network). Members hide a
  contribution for themselves (`ui.hiddenContributions`), the Admin portal-wide (`plugins.slot_settings`).
- **Rationale**: no plugin code in Portalab's page (spec clarification); slots inherit the interface's
  tokens, safe mode and accessibility like any Portalab component.

## R11 — Live channels

- **Decision**: `ctx.live.publish(topic, payload, audience)` writes to 001's live outbox
  (`core.live_event`, filtered per subscriber by audience user ids and/or a plugin permission), topic
  `plugin.<key>.<topic>`, payload ≤ 8 KiB, 20/s per plugin (burst 100); recipients who blocked the author
  (012) are removed by Portalab when the payload names an `author`. Presence: the parent tells the child
  `joined`/`left` for its topics from SSE subscriptions (`ctx.live.on_presence`). On quarantine, the
  plugin's topics are closed.
- **Rationale**: the plugin holds no connection (FR-012); the existing SSE stream carries it.

## R12 — Manifest, migration of 023's plugins

- **Decision**: manifest `schema_version = 2` adds `runtime = "confined"` (default for v2), `capabilities`
  (the closed list of FR-005, each with its parameters: hosts, portal operations, job permissions, live
  topics, quota), route labels, `slots`, secret settings. `schema_version = 1` plugins with code are
  `runtime = "in_process"`. A data migration sets `plugins.allowUnconfined = true` on an install that already
  has an in-process code plugin, `false` otherwise; while false, in-process code plugins are **held**
  (`held_unconfined`) with the Admin told how to migrate. Migration = new version with `runtime = "confined"`,
  reviewed like any update; data untouched (same schema). The administration shows a permanent warning for
  every unconfined plugin.

## R13 — Product types

- **Decision**: 023's `product_type` registration is proxied; the shop keeps buying, coins, ownership,
  refunds (015); activation, deactivation and refund hooks run in the child within 10 s; a failed activation
  follows 023's `ActivationService` rule (refund or pending, never lost). The card is a 028 element or
  blocks.

## R14 — Deployment hardening (#144)

- **Decision**: (a) the image already runs as user 10001: add `read_only: true` with `tmpfs` for `/tmp` in
  the compose example and an image check (`portalab doctor`) that warns when the code folders are writable;
  (b) **outbound allow-list**: one place builds every outgoing HTTP client (`connectors/http_base.py`,
  pack sources, sign-in providers, R8); `security.egressAllowList` (off on upgrade, documented on) refuses
  any other host, logged; (c) **per-module database privileges**: one `NOLOGIN` role per module schema;
  each module's units of work `SET LOCAL ROLE portalab_<schema>`; behind `security.moduleRoles` (off by
  default) until the whole suite passes with it on — cross-schema reads found are listed and moved behind
  capabilities; (d) **audit off the machine**: an outbox consumer copies each audit entry as it is written
  to syslog (RFC 5424 over TCP/TLS) and/or an append-only JSON-lines file on a mounted path.
- **Rationale**: (c) is the largest change of this spec and the most likely to break something; it is
  delivered last and switchable.

## R15 — Authoring: SDK, simulator, template, analysis

- **Decision**: `portalab.sdk` keeps 023's surface plus `ctx.db`, `ctx.portal`, `ctx.http`, `ctx.live`,
  `ctx.settings`, slot and block types; `portalab plugin new <key>` writes a template; `portalab plugin
  simulate <dir>` runs the plugin **confined** against a simulated Portalab (storage in a temporary schema of
  a given database, or refused without one; portal operations answered from sample data; network refused
  unless `--allow-host`; live and notifications printed); `portalab plugin validate` reports the requested
  capabilities in the Admin's words and every blocking finding (unknown capability, slot, label, missing
  privacy hooks, unconfined code).

## R16 — Examples

- **Decision**: five examples under `examples/plugins/`: `forum` (storage, operations, permissions, nav,
  pages with `thread`, notifications, search, events, privacy, committing « publish »), `chat` (live topics,
  presence, mentions, moderation, blocks), `commission` (a product type « Avatar commission »: schema,
  activation creating a request, refund), `moments` (timestamped notes in the player: `player.overlay`,
  `player.button`, member and admin settings), `home-sections` (`home.section` ×2, nav, a page, a 028 look).
  Each passes `validate` and runs confined in CI.

## R17 — Tests and the isolation campaign

- **Decision**: a **probe plugin** (`tests/fixtures/plugins/probe`) that tries, one by one and only when asked
  by the test: reading a core table, `RESET ROLE`, `set_config('role')`, opening a socket, connecting to
  the database port, resolving and calling an unlisted host and a private address, reading the secret key
  file, `/proc/1/environ`, another plugin's scratch folder, writing the plugin's own code, forking, exec,
  signalling the parent, allocating past its memory, looping past its time, flooding live and storage. Each
  attempt must fail, be recorded and nothing outside change (SC-001); the portal's journeys run while it
  crashes and loops (SC-002). Probes are described in neutral terms; none exfiltrates anything real.
