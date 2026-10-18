# Contract: HTTP API changes

All under `/api/v1`, problem+json errors (001), CSRF on writes, default deny.

## Members

| Method | Path | Permission | Notes |
|--------|------|------------|-------|
| GET/POST | `/plugins/{key}/{path}` | the route's | 023's dispatcher, now proxied to the child for confined plugins; a `committing` route without `confirmation` → **409** `plugin.confirmation_required` `{confirmation, summary: {title, lines[], amount?}}`; resend with body field or header `X-Portalab-Confirmation`; wrong/used/expired token → 409 again with a new token |
| GET | `/plugins/slots?slot=…&context=…` | member | contributions for a slot (only enabled plugins, their permission, not hidden): `[{id, plugin, slot, blocks|element, data_url, order}]` |
| GET | `/plugins/{key}/slots/{id}/data?…` | the contribution's | calls the plugin's `slot_data` handler with the slot context (e.g. `item`, `from_s`, `to_s`) |
| PUT | `/me/preferences` | self | `ui.hiddenContributions`, `ui.coreOrder` (020's endpoint, new keys) |

## Administration (`plugins.manage`, sensitive ones confirmed by 020's `authz.confirmation_required`)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/admin/plugins/{key}` | 023's detail + `runtime`, `confinement`, `grants`, `requested_capabilities` (plain-words descriptions, en/fr), `attempts_recent`, `network_hosts`, `warning` (unconfined / weak) |
| PUT | `/admin/plugins/{key}/versions/{v}/grants` | `{capabilities: [names]}` — must equal the requested set to enable; sensitive |
| DELETE | `/admin/plugins/{key}/grants/{capability}` | revoke now; sensitive |
| GET | `/admin/plugins/{key}/attempts?before=` | paged attempts |
| PUT | `/admin/plugins/{key}/secrets/{name}` | `{value}` write-only; 204; sensitive |
| DELETE | `/admin/plugins/{key}/secrets/{name}` | clear; sensitive |
| GET/PUT | `/admin/plugins/slots` | portal-wide order/visibility per slot |
| GET | `/admin/plugins/runtime` | kernel confinement available? `{landlock_abi, seccomp, ok, weak_allowed, unconfined_allowed}` |

## Internal (not HTTP)

`portalab.acting_principal` ASGI scope key, set only by `ctx.portal.call`'s in-process transport, honoured by
the authentication dependency; any HTTP request carrying a header of that name is ignored.
