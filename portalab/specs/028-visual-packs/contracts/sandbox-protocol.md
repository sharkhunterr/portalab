# Sandbox Protocol (028)

The frame: `<iframe sandbox="allow-scripts" referrerpolicy="no-referrer" src="/api/v1/visuals/sandbox">`
(opaque origin; session required to load it, R13). Its CSP: `default-src 'none'; script-src
'sha256-<bootstrap>' blob:; style-src 'unsafe-inline' blob:; img-src blob: data:; font-src blob: data:;
media-src blob: data:; connect-src 'none'; worker-src 'none'; child-src 'none'; frame-src 'none';
object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'`.

Messages are accepted only from the expected window (`event.source`), never by origin.

## Host → frame

| message | when |
|---|---|
| `{type: "run", source, element: {type, look}, context}` | after `loaded`; `source` = module text fetched by the host; `context` = what it knows **now** (an update while the frame loaded is never lost) |
| `{type: "context", context}` | what the element knows changed |
| `{type: "asset", id, buffer, mime}` / `{type: "asset", id, error}` | answer to an asset request (own element folder only) |
| `{type: "ping", n}` | every 2 s (R14) |

## Frame → host

| message | rule |
|---|---|
| `loaded`, `ready`, `error {message ≤ 300}` | `ready` within 4 s or the element is stopped |
| `pong {n}` | 3 missed ⇒ stopped |
| `asset {id, path}` | relative path inside the element's folder (`safeAssetPath`) |
| `navigate {key}` | navigation only; key must be one of `context.sections[].entries[].key` / section keys; ≤ 1 per 400 ms |
| `expand {open}` | navigation only; within the declared `nav.expands` |

## Context per element type

| type | context |
|---|---|
| `navigation` | `sections[{key, label, icon (SVG markup from the portal), active, entries[{key, label, icon, active}]}]`, `current`, `colors`, `fonts`, `strings{open, close, mainNav}`, `counts{unread}`, `me{level, coins}`, `device`, `layout`, `reducedMotion` |
| `level_up`, `effect` | `{level?, text?, reducedMotion}` |
| `booster_opening`, `card_reveal` | `{phase, rarity?, index?, count, reducedMotion}` — never product data (R23) |
| `widget` | `{data: {<contract>: projected value \| {state: "forbidden"\|"error"\|"loading"}}, config, size {width, height, rows, form: line\|column\|block\|tall}, colors, fonts, locale, reducedMotion}` (R26); the member resizes it within its declared sizes |
| `widget_option` (js) | the same, and `widget {key, state, data}`: the widget it is shown on and that widget's own data |
| `ambient` (js) | `{reducedMotion, size}` |

Reduced motion: the host passes `reducedMotion: true`; moments show their still frame or nothing; the host
skips `js` moments entirely when the member asked for no animation.
