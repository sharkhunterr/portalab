# Implementation Plan: Services & Health

**Branch**: `006-services-health` | **Date**: 2026-10-01 | **Spec**: `specs/006-services-health/spec.md`
**Roadmap**: Phase 2 step 6 *Connectors / Services* (state, probes, maintenance) and Phase 4 step 13 *Health / Maintenance / Incidents* (detail page, history UI, incident links).

## Summary
Module `health` derives and serves service state, availability/uptime, recent errors, health history, maintenance windows, infrastructure metrics and privileged server operations, and assembles the service detail page from independent sections. It keeps Service State, Incident, Maintenance, Ticket and Sync State distinct. Sync mechanics stay in 005, incident lifecycle in Support (016, through a port), portal self-observation in 025.

## Technical Context
**Language**: Python 3.12 · **Deps**: none new · **Storage**: schema `health` (samples partitioned) · **Testing**: pytest on real PG + fake connector · **Constraints**: stale ⇒ Unknown never Operational; maintenance ≠ Unavailable; permission-based response shapes; no secrets in errors/metrics · **Scale**: tens of services, probe cadence configurable.

## Constitution Check — PASS
IX graceful degradation per section · XIII observability signals · VI/VII permission-tiered visibility · XIV deterministic state derivation · II/XX no second incident/monitoring system · IV events with `occurred_at`. No violations.

## 1. Architecture
```
scheduler ─▶ probe_service job ─▶ provider(service.health_probe) ─▶ health_samples
                                   breaker state (005) + active maintenance ─┐
StateDeriver ◀────────────────────────────────────────────────────────────────┘ ─▶ service_state + state_history ─▶ service.status_changed
rollup job ─▶ health_rollups · maintenance jobs (start/end at instants) · metrics job ─▶ infra_samples
Detail API: sections [state|availability|errors|maintenance|incidents|tickets|sync|infra|history] each independent + permission-filtered
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `ProbeScheduler`/`ProbeRunner` | schedule probes, write samples | `core.jobs`, 005 | job `probe_service` | per-service isolation, timeouts | probe tests |
| `StateDeriver` | state from samples+breaker+maintenance, staleness | config thresholds | pure function | deterministic; Unknown on no signal | table-driven tests |
| `AvailabilityService` | uptime/availability from rollups | `health_rollups` | API | marks gaps | rollup tests |
| `MaintenanceService` | CRUD, start/end jobs by instants, events | `core.jobs`, 007 | API | absolute instants | maintenance tests |
| `InfraMetricsService` | fetch/store metrics, per-metric availability | capability | API | `infrastructure.read` | metrics tests |
| `OperationsService` | list/execute server operations | capability | API | sensitive, confirmation, audited | operations tests |
| `IncidentLinkService` | link/display incidents via `support.incidents` port | port | API | no local incident model | link tests |
| `DetailAssembler` | independent sections with state + permission tiers | all | `GET /services/{id}/health` | section failure isolated | degraded tests |
| `health.service_state` capability | read model for other modules | all | capability | `as_of` freshness | contract tests |

## 3. Data Model / 4. Contracts
`data-model.md`, `contracts/health-contracts.md`.

## 5. Events
Produced: `service.status_changed`, `service.health_recorded`, `maintenance.scheduled|rescheduled|started|ended|cancelled` (payload carries `schedule_version`; consumed by 010 reminders, 011 calendar), `service.operation_performed` (007 publisher; dedup `(service, to_state, state_seq)` / `(maintenance_id, transition)`). Consumed: `sync.*` and `service.*` from 005 (breaker/state inputs), `incident.*` (display links, from 016). Failure: idempotent state derivation (recompute from inputs).

## 6. Permissions & Security
Standard: `services.read` (state, availability); `infrastructure.read` (metrics, uptime details per registry default); `services.manage` (maintenance create/edit, operations — sensitive, confirmation, audited). Shape differences enforced server-side; errors/metrics redacted.

## 7. Configuration (declared)
`health.probeIntervalSeconds` (per-service override), `health.degradedLatencyMs`, `health.unavailableAfterFailures`, `health.staleAfterSeconds`, `health.sampleRetentionDays`, `health.infraRetentionDays`, `health.rollupRetentionMonths`.

## 8. External Integrations
Only through capabilities `service.health_probe`, `infrastructure.metrics`, `server.operations`; failure ⇒ typed unavailable results; metrics partially available ⇒ per-metric `NotAvailable` (never zero).

## 9. Error Handling & Resilience
Probe timeout ⇒ failed sample; monitor down ⇒ Unknown; metrics provider down ⇒ section unavailable; operation against unreachable host ⇒ actionable error; derivation recomputes after restart; maintenance job missed ⇒ reconciled at startup by comparing windows to now.

## 10. Observability
Probe latency/failures per service, state-change counts, section failure rates, rollup lag; feeds 025.

## 11. Testing Strategy
Unit: state derivation table incl. staleness/maintenance precedence; rollups. Integration: outage ⇒ Unavailable once, recovery; maintenance window flips state at instants; DST-independent absolute-instant tests; section isolation; permission tiers (standard vs `infrastructure.read`); operations audited. Security: permission matrix, redaction. Migration: upgrade from 005.

## 12. Migration / Versioning
Alembic `health`; partitions via 021 helper; state derivation rules versioned in code with history retained.

## 13. Cross-Spec Dependencies
Prerequisites: 001, 003, 005 (services, breaker, sync state), 007, 020, 021 (retention). Port to Support 016 (`support.incidents`). Exposes `health.service_state`, maintenance events to 011 Calendar, 009 Dashboard, 010 Notifications, 025. Roadmap slicing: backend phases 1–7 at step 6; UI/detail page + incident links at step 13.

## 14. Implementation Phases
1 Data & config → 2 Probes & state derivation → 3 Rollups/availability/errors → 4 Maintenance → 5 Infra metrics & operations → 6 Detail assembler & API → 7 `health.service_state` capability → 8 UI (step 13) & incident links, tests.

## 15. Technical Decisions & Trade-offs
`research.md` R1–R8: derived state, five distinct concepts, rollups, capability-based probes/metrics/operations.

## 16. Risks / Open Technical Questions
- **R1** Incident implementation lives in 016; until then incident links use the port with an empty provider.
- **R2** Operation catalogs are provider-defined; permissions per operation need a registry (kept simple: flag + audit).
- **R3** Probe cadence vs load for many services — configurable.

## Project Structure
```text
backend/src/portalab/modules/health/{probes,state,rollups,maintenance,infra,operations,detail,api,models}/
backend/migrations/health/versions/ · frontend/src/features/services/ (overview, detail)
```
