# Implementation Plan: Connectors

**Branch**: `005-connectors` | **Date**: 2026-10-01 | **Spec**: `specs/005-connectors/spec.md`
**Roadmap**: Phase 2 step 6 *Connectors / Services* (with spec 006).

## Summary
Module `connectors` provides the integration layer: the Connector SDK, service instances and their lifecycle (configure, test, enable, disable, disconnect), capability provisioning through the registry, the sync runner (idempotent, serialized per service, provenance-preserving), sync history, resync, discovery candidates, compatibility checks, and the circuit breaker. Domain data ingestion goes through `RecordSink`s owned by consuming modules; health presentation and metrics belong to 006; concrete connectors belong to their domain plans.

## Technical Context
**Language**: Python 3.12 · **Deps**: httpx (baseline) · **Storage**: schema `connectors` · **Testing**: pytest on real PG with a fake external HTTP service · **Constraints**: no module-specific code in connectors; no deletion on outage/disconnect; credentials encrypted; per-call timeouts · **Scale**: tens of services.

## Constitution Check — PASS
II/V capability decoupling & source of truth · IX isolation and graceful degradation · VI credential protection · IV events for state/sync · III connectors extensible via SDK/plugins · XIII observability. No violations.

## 1. Architecture
```
admin API ─▶ ServiceManager ─▶ connectors.services ──▶ CapabilityRegistry.provide/withdraw (001)
scheduler ─▶ job sync_service(dedup (service,window)) ─▶ SyncRunner (advisory lock per service)
     Connector.sync() ─▶ SourceRecord stream ─▶ RecordSink (module-owned) ─▶ events (sync.*, domain events via sink)
Live calls ─▶ provider wrapper (timeout/retry/circuit breaker, typed results with as_of/provenance)
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `ConnectorRegistry` | register connectors/manifests | kernel | `register_connector` | duplicate keys rejected | registry tests |
| `ServiceManager` | CRUD, state machine, enable/disable/disconnect, capability (de)registration | `core.db`, 001 registry, `core.secrets` | API | disable/disconnect never delete data | lifecycle tests |
| `ConnectionTester` | run `test_connection`, record result, no state change | connectors | API | secrets redacted | test-connection tests |
| `DiscoveryService` | probe operator targets, candidates, confirm/decline | connectors | API | never auto-enable | discovery tests |
| `CompatibilityChecker` | manifest vs portal/capabilities/permissions | registry | hook for 020 toggles | refuse/warn, keep prior state | compat tests |
| `SyncScheduler` + `SyncRunner` | schedule, lock, execute, counts, history, resync | `core.jobs`, events | jobs/API | one run per service; idempotent; partial failure keeps data | sync tests |
| `RecordSink` registry | modules register ingestion per capability | capabilities | `register_sink` | upsert/deactivate only | sink contract tests |
| `CircuitBreaker` | per-service open/half-open/closed | `core.db`/memory | wrapper | feeds state `unavailable` | breaker tests |
| `ConnectorHttpClient` | safe outbound HTTP | httpx | SDK | size/time limits, redaction | http tests |
| `ConformanceKit` | tests every provider/connector must pass | testkit (001) | pytest kit | reusable | self-test with `fake` connector |
| `connectors.api` | endpoints per contract | all | OpenAPI | `require()` everywhere | permission matrix |

## 3. Data Model / 4. Contracts
`data-model.md`, `contracts/connector-contracts.md`.

## 5. Events
Produced: `service.connected|disconnected|status_changed`, `sync.started|completed|failed`, `connector.discovered|compatibility_checked|resync_requested` via the 007 publisher (dedup `(service, run)` / `(service, to_state, seq)`; `occurred_at` = event time, never receipt/sync time). Consumed: `service.disconnected` observers elsewhere; none inside. Failure: outbox retry.

## 6. Permissions & Security
`services.read`, `services.manage`, `connectors.manage` (sensitive), `services.purge` (021). Enable/disable/disconnect/resync-large audited with confirmation. Credentials write-only; outbound calls limited to the configured base URL host; response size/time limits.

## 7. Configuration (declared)
`connectors.defaultSyncIntervalSeconds`, `connectors.circuit.failureThreshold`, `connectors.circuit.cooldownSeconds`, `connectors.http.timeoutSeconds`, `connectors.http.maxResponseBytes`, `connectors.fieldPriority.<domain>` (per-field source priority tables, CD-026), `connectors.resync.confirmDeleteRatio`.

## 8. External Integrations
Defined by SDK only; each concrete service (Plex, Radarr, Sonarr, Seerr, RomM, Grimmory, …) is added later as a connector package with the conformance kit. Contract per integration: auth, timeout, unavailable ⇒ typed result + stale, malformed ⇒ `InvalidResponse`, retry bounded.

## 9. Error Handling & Resilience
Timeout/unavailable ⇒ typed result, breaker counts, last-known data served as stale · malformed payload ⇒ record rejected + counted, run `partial` · auth failure ⇒ state `error` with `AuthenticationFailed`, no retry storm · sink exception ⇒ run marked failed for that batch, earlier batches kept · overlapping trigger ⇒ 409/skipped · worker crash ⇒ lock released, run resumed/restarted from cursor.

## 10. Observability
Per service: state, last success, run duration, counts, failures, breaker state, latency; structured logs with correlation id and redaction; consumed by 006/025.

## 11. Testing Strategy
Unit: state machine, breaker, manifest checks. Integration (real PG + fake HTTP service): enable → capability resolves; two providers ordering; outage keeps data; resync never touches other provenance; duplicate/late records idempotent; discovery never auto-enables. Contract: conformance kit against `fake`; RecordSink kit. Security: write-only secrets, redaction, permission matrix, same-host redirect policy. Migration: upgrade from 007.

## 12. Migration / Versioning
Alembic for `connectors`; connector manifests semver'd; `SourceRecord` schema versioned; capability Protocols semver'd (001).

## 13. Cross-Spec Dependencies
Prerequisites: 001 (registry, jobs, secrets, http), 003, 007 (events), 020 (toggles/config), 021 (purge/retention). Exposes: SDK, `RecordSink`, `ServiceManager`, conformance kit, state/sync events. Used by: 006 (health/state), 024 Media and other domains (sinks, providers), 025 (observability), 010/019 (events).

## 14. Implementation Phases
1 Data & registry → 2 ServiceManager + http client → 3 Test/discover/compat → 4 Sync runner & sinks → 5 Circuit breaker + provider wrapper integration → 6 Resync & history → 7 API/UI → 8 Conformance kit & hardening.

## 15. Technical Decisions & Trade-offs
`research.md` R1–R10: sinks owned by modules, deactivate-not-delete, advisory-lock serialization, breaker, SDK-only scope.

## 16. Risks / Open Technical Questions
- **R1** Per-field priority tables (CD-026) live in config; their shape is finalized with Media's plan.
- **R2** Capability catalog grows with domain plans — this plan fixes only the mechanism.
- **R3** Long-running syncs vs job timeouts: runner checkpoints cursors and resumes.
- **R4** Single-node scheduler; no HA.

## Project Structure
```text
backend/src/portalab/modules/connectors/{sdk,registry,services,discovery,sync,breaker,http,api,models}/
backend/src/portalab/connectors/fake/ (conformance fixture) · backend/migrations/connectors/versions/
```
