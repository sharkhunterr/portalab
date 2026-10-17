# Contract: Broker protocol (sandbox ⇄ host)

Extends 028's sandbox protocol (`specs/028-visual-packs/contracts/sandbox-protocol.md`). Messages travel by
`postMessage` between the host page (Portalab's origin) and a frame of the pack origin (opaque). The bootstrap
(hashed in the frame's CSP) is the only code that touches the channel before the pack's module.

## Frame kinds

| kind | document | used by |
|---|---|---|
| `script` | `/sandbox/script` | 028 navigations, widgets, scenes, options |
| `app` | `/sandbox/app` | `interface_app` (full screen, below the trust layer) |

## Host → frame

| message | fields | notes |
|---|---|---|
| `run` | `source, element, context` | 028; `context` for an app: `{form, language, reducedMotion, textScale, colorScheme, page, equivalents, operations, components}` |
| `context` | `context` | 028 |
| `asset` | `id, buffer, mime, error` | 028 |
| `ping` | `n` | 028 heartbeat (answered `pong`) |
| `result` | `id, ok, data?, problem?` | answer of a `call` |
| `event` | `name, data` | a subscribed topic, or a host component's event (`booster.revealed`, `player.ended`) |
| `quality` | `level: "normal"\|"low"` | budget (research R12) |

## Frame → host

| message | fields | rules |
|---|---|---|
| `ready`, `error`, `pong`, `asset` | | 028 |
| `navigate` | `key` | 028; for an app, a view key or an equivalent's key |
| `call` | `id, operation, params` | `operation` = `"METHOD /api/v1/…template"`; refused unless declared ∧ accepted ∧ not forbidden; committing ⇒ trust layer first |
| `subscribe` | `topics` | only declared topics |
| `place` / `move` / `unplace` | `id, component, props, rect` | declared ∧ accepted components only |
| `health` | `fps, memory?` | every 2 s (bootstrap) |
| `texts` | `texts` | Test step probe (bootstrap text walker) |
| `exit` | — | the shortcut caught by the bootstrap (Alt+Shift+P) |

## Answers

- Success: `data` = the API's JSON with Portalab image/file addresses replaced by asset handles
  `{asset: "<id>"}` the frame resolves with `asset` (bytes).
- Refusal: `problem` = `{code, title}` — `ui.interface_operation_refused` (not declared/accepted/forbidden),
  `ui.interface_cancelled` (the member declined the confirmation), `ui.interface_rate_limited`, or the API's
  own problem code unchanged.
