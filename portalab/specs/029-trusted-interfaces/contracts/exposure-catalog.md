# Contract: Exposure catalog

## `GET /api/v1/exposure` (members)

```json
{"operations": [{"operation": "GET /api/v1/media", "exposure": "read",
                  "words": {"en": "…", "fr": "…"}, "topics": []}],
 "components": [{"component": "media.player", "words": {…}, "props": {…}}]}
```

Lists only non-forbidden labels. Cached per release (ETag).

## Rules

1. Forbidden prefixes win: `/api/v1/admin`, `/api/v1/auth`, `/api/v1/users`, `/api/v1/roles`,
   `/api/v1/groups`, `/api/v1/permissions`, `/api/v1/grants`, `/api/v1/audit`, `/api/v1/maintenance`,
   `/api/v1/privacy`, `/api/v1/plugins`, `/api/v1/connectors`, `/api/v1/me/security`, `/api/v1/me/sessions`,
   `/api/v1/me/seal`, `/api/v1/me/account`, `/api/v1/me/settings`, `/api/v1/exposure` itself,
   `/api/v1/visuals/*` (pack plumbing).
2. A route a module does not label is forbidden.
3. `read` only on `GET`; `GET` routes never `action`/`committing`.
4. `committing` requires `confirm` words: purchases, booster openings, media requests, deletions,
   publications (posts, comments, tickets), anything moving Coins or making content public.
5. A test lists every route of the application with its resolved label; adding a route without a label
   keeps it forbidden (and the test prints it for the author).

## Server check (`X-Portalab-Interface`)

A request with `X-Portalab-Interface: <pack>@<sha16>/<element>` is refused `403
ui.interface_operation_refused` unless that element is live and its accepted operations contain the
request's operation; rate limited per (member, interface); committing ones audited (`interface.operation`).
