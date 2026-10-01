# Implementation Plan: Portal Observability

**Branch**: `025-observability` | **Date**: 2026-10-01 | **Spec**: `specs/025-observability/spec.md`
**Roadmap**: Phase 2 step 7 *Observability*.

## Summary
Module `observability` lets the portal observe itself: two-axis (technical/functional) component health, structured error management, rule-based anomaly detection with controlled escalation to the existing incident system, performance-phase attribution, AI/plugin/connector/automation/event/sync observability through one registration model, alerting through Notifications, an action-first admin overview, trends with retention, and a fail-open design. It complements 006 (external service health), never replaces it, and creates no incident, notification or audit model of its own.

## Technical Context
**Language**: Python 3.12 · **Deps**: none new (optional Prometheus text format hand-rendered) · **Storage**: schema `obs` (partitioned samples) · **Testing**: pytest real PG, fault injection · **Constraints**: fail-open, no secrets/PII/AI content stored, no hard-coded thresholds · **Scale**: minute-level samples for tens of components.

## Constitution Check — PASS
XIII observability & auditability (core) · IX resilience (fail-open) · VII privacy (no AI content, redaction) · II/XX single incident/notification/audit/monitoring owner · XIV deterministic detectors · VI permissions. No violations.

## 1. Architecture
```
kernel hooks (metrics, Timer(phase), errors.record) ─▶ bounded in-memory queue ─▶ Collector job ─▶ obs.metric_samples / obs.errors
declare_observable(...) ─▶ ComponentRegistry ─▶ HealthEvaluator (technical + functional) ─▶ obs.component_health / history
Detectors ─▶ obs.anomalies ─▶ EscalationPolicy ─▶ support.incidents port · notifications.send_alert · events (007)
Overview API ─▶ ranked problems + DiagnosticAction descriptors ─▶ Control Center panel (020)
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `MetricsRegistry` (kernel) + `Timer` | counters/histograms, phase timers | none | hooks | non-blocking | overhead/drop tests |
| `Collector` | drain queue, aggregate, write samples, rollups | `core.db`, jobs | job | bounded, fail-open | collector tests |
| `ErrorRecorder` | fingerprint, redact, upsert counts, states | `core.db` | `errors.record` | no secrets/PII | fingerprint/redaction tests |
| `ComponentRegistry` + `HealthEvaluator` | declare components, evaluate both axes | config thresholds | `declare_observable` | functional ≠ technical | table-driven tests |
| `Detectors` | rule-based anomaly detection | samples/errors | registry | params via config | detector tests |
| `EscalationService` | candidate → validate → incident, dedup by fingerprint | `support.incidents`, notifications | policy | one open incident per fingerprint | escalation tests |
| `OverviewService` | ranked problems, diagnostics descriptors | all | API | action-first ordering | ranking tests |
| `AlertService` | alerts via Notifications port, events for Automations | ports | internal | no own channel | alert tests |
| `ObservabilityAPI` | endpoints | authz | OpenAPI | `require()` | permission matrix |
| Component adapters | event consumers, sync, automations, plugins, connectors, AI, jobs, db | owning modules' metrics | `declare_observable` | metadata only for AI | adapter tests |

## 3. Data Model / 4. Contracts
`data-model.md`, `contracts/observability-contracts.md`.

## 5. Events
Produced (007 publisher; dedup `(component, axis, to_state, seq)` / fingerprint+window): `observability.health_changed`, `observability.error_recorded` (first occurrence/state changes), `observability.anomaly_detected`, `observability.alert_raised`. Consumed: `events.consumer_dead_lettered`, `sync.failed`, `service.status_changed`, `plugin.*`, `automation.suspended` (as observation inputs). Failure: observation is best-effort; evaluation idempotent from stored samples.

## 6. Permissions & Security
`observability.read` (Admin full; Support redacted per registry default), `observability.manage` (ack/resolve/validate/dismiss — audited). No raw log browser; no secrets/PII/AI content stored; `/metrics` off by default and token-protected; diagnostic actions executed only through owners' permission-checked APIs.

## 7. Configuration (declared)
`observability.sampleRetentionDays`, `observability.rollupRetentionMonths`, `observability.errorRetentionDays`, `observability.detectors.<name>.*`, `observability.escalation.autoSeverity`, `observability.escalation.requireValidation`, `observability.thresholds.<component>.*`, `observability.metricsEndpointEnabled`.

## 8. External Integrations
None required; optional Prometheus-format endpoint for operators' own tooling.

## 9. Error Handling & Resilience
Queue full ⇒ drop oldest + count drops · store down ⇒ buffer then drop, request path unaffected · detector exception ⇒ isolated, counted · incident port unavailable ⇒ anomaly stays `pending_validation`, retried · evaluator failure ⇒ component `unknown` rather than green.

## 10. Observability (of observability)
Self-metrics: queue depth, drops, collector lag, detector failures, evaluation duration; reported as its own component so failures are visible.

## 11. Testing Strategy
Unit: health evaluation table (tech up/functional failing), fingerprinting, detector rules on synthetic series, ranking. Integration: end-to-end sync-failure scenario ⇒ functional failing + anomaly ⇒ single incident; fail-open under DB outage; redaction (no secrets/PII/AI content); phase attribution (slow external vs internal). Security: permission matrix, Support redaction. Migration: upgrade from 006.

## 12. Migration / Versioning
Alembic `obs`; samples partitions via 021 helper; detector parameter sets versioned in config.

## 13. Cross-Spec Dependencies
Prerequisites: 001 (kernel hooks), 003, 007, 020, 021, 005/006 (inputs). Ports to Support 016 and Notifications 010 (stubs until then). Exposes `observability.health`, `declare_observable`. Used by 020 Control Center, 009, 018 (ask-AI diagnostics later), every module's contributions.

## 14. Implementation Phases
1 Kernel hooks & Timer → 2 Data & collector → 3 Error recorder → 4 Component registry & evaluator → 5 Adapters for existing modules → 6 Detectors & escalation → 7 Overview/API/diagnostics → 8 Alerts, trends, UI, tests.

## 15. Technical Decisions & Trade-offs
`research.md` R1–R11: in-process metrics, rule-based detection, separate store, phase timers, descriptor-based diagnostics.

## 16. Risks / Open Technical Questions
- **R1** Detector tuning (false positives) — parameters in config; start conservative.
- **R2** Kernel hooks must be added early to modules built before this step (001–007): retrofit tasks included.
- **R3** Incident/notification ports are stubs until 016/010.
- **R4** Single-process queue; multi-process (worker + API) requires per-process flush — handled by writing samples from both.

## Project Structure
```text
backend/src/portalab/core/metrics.py (hooks) · backend/src/portalab/modules/observability/{collector,errors,components,detectors,escalation,overview,alerts,api,models}/
backend/migrations/observability/versions/ · frontend/src/features/admin/observability/
```
