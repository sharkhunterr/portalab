# Contract: `interface_app` element (pack format 1, addition)

```json
{
  "type": "interface_app",
  "look": "teletext",
  "names": {"en": "Teletext", "fr": "Télétexte"},
  "render": {"kind": "app", "file": "app.js"},
  "app": {
    "forms": ["desktop", "tablet", "phone"],
    "operations": ["GET /api/v1/media", "POST /api/v1/media/requests"],
    "components": ["media.player"],
    "topics": ["notifications.created"],
    "equivalents": {"/": "100", "/media": "200", "/progression": "300", "/marketplace": "400"},
    "light": null
  },
  "preview": "preview.png",
  "economy": {"sold": false}
}
```

The module: `export default (root, api) => { … }` where `api` is 028's (`asset`, `onContext`, `navigate`,
`context`) plus:

| api | |
|---|---|
| `call(operation, params) → Promise<data>` | rejects with `{code, title}` |
| `subscribe(topics, listener) → unsubscribe` | |
| `place(component, props, rect) → handle {move(rect), remove()}` | |
| `onQuality(listener)` | `"normal"`/`"low"` |

Equivalents: an address stands for itself only; `"/wiki/*"` stands for every address under `/wiki` (R19: any
other address shows Portalab's own page).

Limits: pack ≤ 60 MB, file ≤ 20 MB, entry module ≤ 8 MB. No network, no storage, no sensors.
