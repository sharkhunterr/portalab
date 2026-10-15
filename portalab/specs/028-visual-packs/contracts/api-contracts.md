# API Contracts: Visual Packs (028)

Prefix `/api/v1`. Errors are RFC 9457 problems with `code`. « Manager » = permission `visuals.manage`
(reserved to the Admin, R17); « Security » = `security.manage`; « Member » = any signed-in member who accepted
the terms. Every Manager write is audited (`visuals.<action>`, actor, pack, version, outcome) and requires the
CSRF header; writes marked † require the confirmation step of 003 (`requires_confirmation`).

## Members

| method | path | answer |
|---|---|---|
| GET | `/visuals/active` | `200 {epoch, elements: ActiveElement[]}`; `ETag: "<epoch>"`, `304` on match |
| GET | `/visuals/files/{pack}/{sha16}/{path}` | the file of a **live** version (inert headers, R12); `404` otherwise |
| GET | `/visuals/sandbox` | the sandbox document (R13), session required; own CSP; `X-Frame-Options: SAMEORIGIN` |
| POST | `/visuals/reports` | `{pack, element, reason: timeout\|error\|slow, detail?}` → `204`; ≤ 10 per session per hour |
| GET | `/visuals/scenes/{booster_key}` | `200 {scene: ActiveElement \| null, parts: {...}}` (default when unbound) |

`ActiveElement` = `{pack, sha, type, look, kind, product, names, file, css[], stage, shape, radius, reveal,
duration, palette, preview, nav, renderer, params, parts, contracts, sizes, refresh}` (absent fields omitted).

## Manager — packs and versions

| method | path | body | answer |
|---|---|---|---|
| GET | `/admin/visuals` | — | `{packs: PackRow[]}` (state, source, current, remote, versions with step/outcomes, owners count, failures) |
| POST | `/admin/visuals/scan` | — | `{found: [{source, pack, version, new, error?}]}` (inbox read) |
| POST | `/admin/visuals/upload` | multipart `file` (≤ `visuals.limits.archive_mb`) | `201 Imported` |
| POST | `/admin/visuals/github` | `{url}` | `201 Imported`; `422 ui.visual_pack_source` (host, size, redirect) |
| POST | `/admin/visuals/updates` | — | `[{pack, offered, installed, update}]` (nothing installed) |
| GET | `/admin/visuals/{pack}/{version}` | — | `VersionDetail {step, outcomes, report, measures, draft, decision, changes, elements (admin addresses)}` |
| GET | `/admin/visuals/files/{pack}/{sha16}/{path}` | — | any version's file (inert headers) |
| POST | `/admin/visuals/{pack}/{version}/measures` | `{results: Measure[]}` (≤ 200) | `204`; step → `tested` |
| PUT | `/admin/visuals/{pack}/{version}/draft` | `{economy, bindings, confirmations}` | `200 VersionDetail`; step → `reviewed` |
| POST | `/admin/visuals/{pack}/{version}/publish` † | `{economy?, bindings?, confirmations: {scripts, replaces[], contracts[]}}` | `200 {pack, version, products: {key: created\|revised\|unchanged}}`; `422 ui.visual_pack_blocked`, `422 ui.visual_pack_confirm` (missing confirmation), `409 ui.visual_pack_claimed`, `409 ui.visual_pack_version_taken` |
| POST | `/admin/visuals/{pack}/{version}/refuse` | `{reason}` | `204`; `409` when published |
| POST | `/admin/visuals/{pack}/state` † | `{state: enabled\|disabled}` | `204`; `409 ui.visual_pack_socle` for the socle |
| POST | `/admin/visuals/{pack}/{version}/rollback` † | — | `200` as publish (decision reused) |
| POST | `/admin/visuals/{pack}/remove` † | — | `200 {outcome: archived\|removed, owners}`; `409` socle |
| POST | `/admin/visuals/{pack}/{version}/purge` | — | `204`; `409` when ever published |
| GET | `/admin/visuals/contracts` | — | the widget data contracts offered (key, permission, refresh, fields, plain-words description) |
| PUT | `/admin/visuals/scenes/{booster_key}` | `{element: uuid \| null}` | `204` (bind a live scene, `*` = default) |

Built-in packs: `upload/github/scan` refuse reserved ids (`409 ui.visual_pack_reserved`); their versions are
`published` by the sync and only `state` (not the socle) and economy edits through the Marketplace apply.

## Security

| method | path | answer |
|---|---|---|
| GET | `/admin/security/blocks` | `{blocks: [{id, kind, label, reason, points, paths, started_at, seconds_left}]}` |
| POST | `/admin/security/blocks/lift` | `{id?}` (none: all) → `{lifted}`; audited |

A blocked account's every request (any session) answers `403 security.blocked` with `Retry-After`; a blocked
address answers requests **without** a session the same way (R29).

## Anonymous surface (R27)

Without a session, only these answer normally; **every other path, existing or not, answers the identical**
`401 {"type":"about:blank","title":"Sign-in required","status":401,"code":"auth.required"}`:

- `POST /auth/login`, `POST /auth/logout`, `GET /auth/oidc`, `GET /auth/oidc/start`, `GET /auth/oidc/callback`
- when self-registration is open: `POST /auth/register`, `POST /auth/verify`
- `POST /auth/deletion/cancel` (single-purpose link)
- `GET /media/remote/{ticket}/session/{path}` (cast ticket)
- `GET /i18n/catalogs/{locale}/{auth|common|errors}`
- SPA: `/` and client routes → `index.html` (the sign-in page); `/assets/<chunk>` only for chunks in
  `public-assets.json`; `/packs/socle/…` (R10)
- `/healthz`, `/readyz`, `/metrics`: only from `observability.health.networks` (R28)
- `GET|POST /admin/first-run`: only while the first run is not completed

## Administration overview (#134, FR-038)

`GET /admin/overview` returns per section only what the caller's permissions allow; a required-action
provider without a declared permission contributes nothing; server errors/slowness need `observability.read`.
