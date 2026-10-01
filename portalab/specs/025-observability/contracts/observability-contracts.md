# Contracts — Observability

## Kernel hooks (non-blocking)
`metrics.counter|histogram(name, labels).observe()` · `Timer(phase)` context manager · `errors.record(component, exc|code, context)` · all fail-open.

## Registration
`declare_observable(component, technical_checks=[...], functional_checks=[...], metrics=[...], diagnostics=[DiagnosticAction])` for core modules, plugins and connectors.
`FunctionalCheck(name, evaluate(ctx) -> Ok|Degraded|Failing|Unknown, reason)` e.g. consumer lag, last sync success, automation failure rate.
`Detector(name, params)` registry; `EscalationPolicy` (config).

## Ports consumed
`support.incidents` (create/attach) · `notifications.send_alert` (alerting; stub until 010) · `automations.trigger` via published events.

## Capability exposed
`observability.health`: `component_health(component)`, `problems(principal) -> ranked list` for Control Center (020) and Dashboard (009).

## HTTP (`/api/v1`)
| Path | Permission |
|---|---|
| GET `/admin/observability/overview` | `observability.read` (ranked: action needed → impact → criticality → age → details) |
| GET `/admin/observability/components/{id}` · `/errors` · `/anomalies` · `/trends` | `observability.read` (Support level = redacted context) |
| POST `/admin/observability/errors/{id}/ack|resolve`, `/anomalies/{id}/validate|dismiss` | `observability.manage` (audited) |
| GET `/metrics` | token or `observability.read`; disabled by default |
Each problem lists `DiagnosticAction` descriptors (target API + required permission); executing them goes through the owning module.
