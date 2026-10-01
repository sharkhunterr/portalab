# Contracts — Services & Health

## Capabilities consumed from connectors (providers)
- `service.health_probe`: `probe(service) -> ProbeResult{reachable, latency_ms, detail}`.
- `infrastructure.metrics`: `fetch(service, metrics) -> MetricSnapshot{metric -> Value | NotAvailable}`.
- `server.operations`: `list(service)`, `execute(service, op, params)`.

## Ports consumed
`support.incidents`: `create(...)`, `link(service_id, incident_id)`, `open_for_service(service_id)` (implemented by Support 016).

## Capability exposed
`health.service_state`: `get(service_id) -> {state, since, last_check_at, availability, as_of}` and `subscribe` via events — used by Dashboard (009), Media (024), Statistics (017), Observability (025).

## HTTP (`/api/v1`)
| Path | Permission |
|---|---|
| GET `/services/health` (overview) | `services.read` (standard shape) |
| GET `/services/{id}/health` | `services.read`; extra sections require `infrastructure.read` |
| GET `/services/{id}/health/history?from&to` | `services.read` (state/availability) · metrics series needs `infrastructure.read` |
| GET `/services/{id}/maintenance`, POST/PATCH/DELETE `/maintenance` | `services.read` / `services.manage` (sensitive for cancel) |
| GET `/services/{id}/operations`, POST `/services/{id}/operations/{op}` | `services.manage`, sensitive, confirmation, audited |
Sections of the detail response each carry `{state, as_of, data}`; unavailable sections never fail the response.
