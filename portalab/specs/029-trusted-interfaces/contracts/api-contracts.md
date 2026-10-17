# Contract: API additions (029)

| route | who | body / answer |
|---|---|---|
| `GET /api/v1/me/seal` | member (self) | `{symbol, colour, word, chosen}` — created at random on first read |
| `PUT /api/v1/me/seal` | member (self) | `{symbol 0–47, colour 0–11, word ≤ 16 \| null}` → the seal; audited (no value logged) |
| `GET /api/v1/exposure` | member | see exposure-catalog.md |
| `GET /api/v1/visuals/interfaces` | member | the live `interface_app` looks the member may choose: `{look, names, descriptions, preview, forms, reads: [words], locked, waiting?}` |
| `PUT /api/v1/admin/visuals/{pack}/{version}/draft` | Admin | 028 + `operations: {element: [operation…]}` |
| `POST /api/v1/visuals/reports` | member | 028 + `reason: "budget"\|"misbehaved"`, `fps?`, `memory?`, `form?` |

Setting (022 preferences API): `ui.interfaceApp` `{desktop, tablet, phone}`.

Pack origin (second port, no API): `GET /sandbox/script`, `GET /sandbox/app` — static documents, CSP per kind,
`frame-ancestors <main origin>`, `Origin-Agent-Cluster: ?1`.

Problem codes: `ui.interface_operation_refused` (403), `ui.interface_rate_limited` (429),
`identity.seal_invalid` (422), `ui.interface_unavailable` (409 when choosing a switched-off interface).
