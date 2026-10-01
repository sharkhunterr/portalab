# Quickstart — Extensibility
1. `portalab plugin validate examples/hello` → manifest OK; Admin uploads/installs it → review screen lists permissions, extension points, events, personal-data flag, schema; approve → state `installed` (restart needed for first code load).
2. Enable → plugin schema/role created, expand migrations run, contributions appear (nav entry, widget, search provider, AI tool, calendar source); disable → **every** contribution disappears (conformance sweep), data intact; re-enable restores.
3. Make a plugin handler raise/timeout repeatedly → errors counted, plugin quarantined, portal and other plugins unaffected; Observability shows `plugin:<key>` degraded.
4. Try a plugin DB query on `identity.users` → permission denied by the plugin role; declared permissions are namespaced and cannot include Admin-reserved keys.
5. Update to 1.1.0: staged → expand migration → restart → probation; force a failing health check → automatic rollback to 1.0.0 with data intact.
6. Dependency: plugin B requires A ≥ 1.2 → enabling B without A is blocked with a named reason; disabling A with B enabled needs confirmation (cascade); cycles rejected.
7. Archive, then purge with export → schema/role dropped, audited; core unaffected throughout; a Marketplace plugin product acquisition activates for the user immediately (or shows needs-configuration).
