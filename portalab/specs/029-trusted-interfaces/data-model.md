# Data Model: Trusted Interfaces (029)

Additions to the data of 028 (`visuals.*`), 022 (`ui` settings) and 002 (`identity`). No table of 028 changes
shape: an `interface_app` element is an `Element` row like any other (its `data` holds the app block), its
accepted operations live in the version's review draft.

## identity.seals (new, migration `identity_00xx_seals`)

| column | type | rules |
|---|---|---|
| `user_id` | uuid PK | FK `identity.users` (migration only), `ON DELETE CASCADE` |
| `symbol` | smallint | 0–47 (index into the 48 seal symbols) |
| `colour` | smallint | 0–11 (index into the 12 seal colours) |
| `word` | text NULL | 1–16 characters, letters/digits/space/`-'`, NFC; never logged |
| `chosen` | boolean | false while assigned at random |
| `updated_at` | timestamptz | |

- Created on first read (`GET /me/seal`) with a random symbol and colour, `chosen = false`.
- Personal data (privacy 021): exported with the account, deleted with it; `word` is `pii()` with tombstone.
- Never exposed by any route an interface may call (its routes are forbidden in the exposure catalog).

## Exposure catalog (code, not a table) — `capabilities/exposure.py`

`OperationLabel`:

| field | type | rules |
|---|---|---|
| `method` | `GET\|POST\|PUT\|PATCH\|DELETE` | |
| `path` | str | the route's template (`/api/v1/media/items/{item}`) |
| `exposure` | `read\|action\|committing\|forbidden` | `read` only on `GET`; `committing` needs `confirm` |
| `words` | `{en, fr}` | plain words shown at review, at choice time and in the SDK |
| `confirm` | `{en, fr}` template \| None | what the trust layer states (placeholders filled from params/answer) |
| `topics` | tuple[str] | live topics this read covers (forwarded to interfaces) |

`ComponentLabel` (host components): `name` (`media.player`, `media.reader`, `community.avatar`,
`marketplace.booster`), `words`, `props` schema.

Resolution: forbidden prefixes → `forbidden`; else the module's declaration; else `forbidden`.

## Element `interface_app` (visuals.elements.data)

```text
type: "interface_app"
look: <key>                              # unique among interface_app looks (claims, 028)
render: {kind: "app", file: "app.js"}
app:
  forms: ["desktop", "tablet", "phone"]  # ≥ 1
  operations: ["GET /api/v1/media", ...]   # each labelled read|action|committing
  components: ["media.player", ...]
  topics: ["notifications.created", ...]           # covered by its read operations
  equivalents: {"/": "home", "/media": "library", ...}   # Portalab path prefix → interface view key
  light: <interface_app look of the same pack> | null
preview, names, descriptions, economy (028; default offered)
```

Validation (analysis, R16): unknown/forbidden/unlabelled operation or component ⇒ blocking; unknown form ⇒
blocking; `light` not an `interface_app` of the pack ⇒ blocking; no `phone` form ⇒ warning; no equivalent for
`/` ⇒ warning; pack ≤ 60 MB, file ≤ 20 MB.

## Review draft (visuals.pack_versions.draft, 028) — addition

```text
operations: {"<element>": ["GET /api/v1/...", ...]}   # accepted per interface_app element
```

Publication requires, for each `interface_app` element, every declared operation and component accepted.
Rollback reuses the recorded acceptance (028 R).

## Setting `ui.interfaceApp` (user scope, 022)

```text
{desktop: <look>|null, tablet: <look>|null, phone: <look>|null}
```

Each value must be a live `interface_app` look the member may use (sold ⇒ owned), else it is refused when
saved; an interface switched off keeps the choice (shown « currently unavailable », 028 T081) while Portalab's
interface shows.

## Browser-local state (per viewer, never server-side)

- `portalab.safe` = `"1"` while safe mode is on (localStorage, sessionStorage fallback).
- `portalab.theme` (028) unchanged.

## Health and budget reports (028 `/visuals/reports`) — addition

`reason` gains `budget` and `misbehaved`; payload `{element, reason, fps?, memory?, form}`; counted on the
element for the Admin (028 element health).

## Test results (028 measures, free JSON) — addition for `interface_app`

```text
{element, profile: "desktop"|"phone", ready_ms, fps, memory_mb?, probes: {exit_control: "ok"|"covered",
 texts: [..], undeclared_calls: [..]}}
```
