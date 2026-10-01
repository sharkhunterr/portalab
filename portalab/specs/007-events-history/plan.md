# Implementation Plan: Events & History

**Branch**: `007-events-history` | **Date**: 2026-10-01 | **Spec**: `specs/007-events-history/spec.md`
**Roadmap**: Phase 2 step 5 *Events / History*.

## Summary
Module `events` owns the Domain Event model, the single append-only history store, idempotency and deduplication (CD-012), consumer delivery isolation, quarantine of invalid input, history queries, retention hooks, and safe replay/reconstruction. It provides the real implementation of the kernel `EventPublisher` port (adopting the envelope used by 002/003/020/021) and shares partition tooling with the audit store, without absorbing it (CD-013).

## Technical Context
**Language**: Python 3.12 · **New deps**: none · **Storage**: schema `events` (partitioned) · **Testing**: pytest on real PG with concurrency tests · **Constraints**: at-least-once delivery, idempotent effects, payloads without PII/secrets, never dedup on timestamp alone · **Scale**: personal/community event volume; partitions handle growth.

## Constitution Check — PASS
IV event-driven domain · V provenance & source-of-truth · IX consumer isolation · XIII observability · XIV deterministic replay · XIX versioned event types · VII privacy (owner-only history, no PII in payload) · II/XX no second event or audit model. No violations.

## 1. Architecture
```
producer tx ─ publish() ─▶ validate (EventType registry) ─▶ events.events + events.dedup_keys (same tx)
                              └ invalid/unknown ─▶ events.quarantine
Dispatcher job ─▶ per-consumer jobs (offset + deliveries) ─▶ handlers (idempotent_effect keys)
                                         └ failure ─▶ retry/backoff ─▶ dead letter (visible)
SSE subscriber (permission-filtered) · HistoryQuery (VisibilityFilter) · ReplayService
```

## 2. Components
| Component | Responsibility | Depends on | Interface | Constraint | Tests |
|---|---|---|---|---|---|
| `EventTypeRegistry` | types, versions, schemas, dedup fields, classes | kernel | `register_event_type` | PII/secret fields rejected | registry/validation tests |
| `Publisher` | validate, derive dedup key, insert in caller tx | `core.db`, registry | `EventPublisher.publish` | atomic with state change; duplicate ⇒ no second row | dedup/atomicity tests |
| `DedupService` | key derivation + `dedup_keys` | registry | internal | never timestamp-only | dedup property tests |
| `Quarantine` | store/release/discard invalid input | `core.db` | API | redacted raw | quarantine tests |
| `Dispatcher` + `ConsumerRuntime` | per-consumer cursors, deliveries, retry, dead-letter, `idempotent_effect` | `core.jobs` | `@consumer` | consumer isolation | isolation/crash tests |
| `HistoryQuery` | user/subject history with permission+privacy | authz, 021 | capability | owner-only default | privacy tests |
| `ReplayService` | ordered rebuild with `replay` flag | consumers | API + CLI | no external effects, originals immutable | replay tests |
| `RetentionTargets` | register events/dedup/deliveries with 021 engine | 021 registry | targets | per class windows | retention tests |
| `AuditLink` | `event_id` correlation to `audit.audit_entries`; shared partition maintenance | 003/021 | column + helper | no second audit model | link test |
| `EventsAdminAPI` | deliveries, dead letters, quarantine, replay | authz | OpenAPI | sensitive actions audited | permission matrix |

## 3. Data Model / 4. Contracts
`data-model.md`, `contracts/events-contracts.md`.

## 5. Events (this module's own)
`events.quarantined`, `events.consumer_dead_lettered`, `events.replay_started|finished` (registered types with dedup fields `(run_id)`).  Catalog of other modules' events is **registered by those modules**, not here.

## 6. Permissions & Security
`events.manage` (view diagnostics privacy-bounded, release/discard quarantine — sensitive), `events.replay` (sensitive, confirmation, audited), history reads through domain permissions + `VisibilityFilter`. Payload validator blocks PII/secret-classified fields; admin payload view redacts personal references per viewer level.

## 7. Configuration (declared)
`events.dispatchBatchSize`, `events.maxDeliveryAttempts`, `events.retryBackoff`, `events.retention.business.months`, `events.retention.technical.days`, `events.dedupKeyRetention`, `events.deadLetterAlertThreshold`.

## 8. External Integrations
Sources (via Connectors, spec 005) publish with `source_system`/`source_event_id`; this module defines nothing connector-specific.

## 9. Error Handling & Resilience
Publisher inside caller tx ⇒ DB failure aborts both state and event · duplicate ⇒ idempotent success · consumer exception ⇒ retry w/ backoff, other consumers unaffected, dead letter after N · dispatcher crash ⇒ resumes from offsets · quarantine write failure ⇒ log + reject safely · late/out-of-order events ordered by `occurred_at` for attribution, `seq` for delivery.

## 10. Observability
Per consumer: lag (seq distance), throughput, failures, dead letters; ingestion: accepted/duplicate/quarantined; replay runs. Exposed via kernel metrics for 025.

## 11. Testing Strategy
Unit: dedup key derivation per strategy; schema validation; PII rejection. Integration (real PG): atomic publish with rollback; concurrent duplicate publish ⇒ one event; two consumers isolated; crash-recovery from offset; dead letter; quarantine; replay safe; partition retention drop. Contract: consumer handler contract kit. Security: history visibility, admin payload redaction, permission matrix. Migration: upgrade from 020.

## 12. Migration / Versioning
Alembic for `events` (partitioned, helper from 021); event types versioned (`type_version`, consumers declare supported versions, upcasters registered per type); additive payload changes within version.

## 13. Cross-Spec Dependencies
Prerequisites: 001 kernel (jobs, db), 003 (authz, audit), 020 (config), 021 (retention, partitions, VisibilityFilter), 002 (types for `user.*`). Exposes: publisher, registry, consumer runtime, history capability, replay. Consumed by: every later spec (005 sync events, 006, 010, 013, 014, 017, 019, 024, …).

## 14. Implementation Phases
1 Data & registry → 2 Publisher + dedup → 3 Quarantine → 4 Consumer runtime → 5 History queries → 6 Retention + audit link → 7 Replay → 8 Admin API/UI, SSE subscriber, tests.

## 15. Technical Decisions & Trade-offs
`research.md` R1–R10: single store, dedup table, per-consumer cursors, replay safety, payloads without PII.

## 16. Risks / Open Technical Questions
- **R1** Migrating 002/003/020/021 event emission from the kernel placeholder to this publisher: contract-compatible by design; add an adapter test.
- **R2** Per-type `dedup_fields` must be chosen carefully by each producer (review checklist).
- **R3** Upcasting strategy for payload version changes — decided per type when first needed.
- **R4** Single-node dispatcher; horizontal scaling would need leader election (out of scope).

## Project Structure
```text
backend/src/portalab/modules/events/{registry,publisher,dedup,quarantine,consumers,history,replay,api,models}/
backend/migrations/events/versions/ · frontend/src/features/admin/events/
```
